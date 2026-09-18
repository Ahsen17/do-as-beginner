# 插件编写指南

面向应用开发者的 do-as-beginner（dab）插件公开 API。读完本页即可编写并注册一个
插件，无需阅读框架源码。

## 概览

插件是**继承**若干**能力面（facet）协议**的普通 Python 类（Litestar PluginProtocol
模式）。框架用 `isinstance` 自动识别插件实现了哪些能力面；全部钩子都是**同步**的
——异步资源通过 lifespan 上下文登记表达，不设 async 钩子。

| 能力面 | 方法 | 调用时机 | 典型用途 |
|-|-|-|-|
| `ServerPlugin` | `name: str`（身份，可省略——缺省用类名） | 注册期校验唯一性 | 必备身份；自动发现的根类 |
| `AssemblyContributor` | `contribute(assembly)` | `settings.configure()` 之前，注册序 | 贡献 INSTALLED_APPS、MIDDLEWARE、Django settings、Celery 任务模块/beat 项、lifespan |
| `SetupPlugin` | `setup()` | `django.setup()` 之后、serve 之前，注册序 | 向 DI 容器注册依赖、启动后台资源 |
| `ShutdownPlugin` | `shutdown()` | 进程优雅关闭时，setup 的反序（LIFO） | 释放同步资源 |
| `CLIPlugin` | `on_cli_init(cli)` | CLI 装配后、命令执行前，注册序 | 向根 Typer 组注入命令 |

## 编写与注册插件

继承需要的协议面，把实例传给 `PluginCore`（varargs）：

```python
from do_as_beginner.server import PluginCore
from do_as_beginner.server.plugins import ServerPlugin, SetupPlugin
from myapp.plugins import MetricsPlugin

class MyPlugin(ServerPlugin, SetupPlugin):
    name = "my"

    def setup(self) -> None: ...

core = PluginCore(MetricsPlugin(), MyPlugin(...))
core.setup()
```

内置插件（otel / redis / qdrant / blobs）经 `ServerPlugin.__subclasses__()`
**自动发现**（无需注册），且总是先于用户插件执行，因此用户插件的 `setup()`
运行时内置插件的 DI 注册已完成。与 `BaseController` 路由注册相同的先例约束：
子类必须被 import 才可见（框架内置插件由框架自身导入）。

## 贡献能力面

### Django 装配贡献

在 `contribute()` 中就地修改 `assembly`：

```python
from do_as_beginner.server.plugins import AssemblyContributor, AssemblyContext

class MyPlugin(ServerPlugin, AssemblyContributor):
    name = "my"

    def contribute(self, assembly: AssemblyContext) -> None:
        assembly.add_installed_app("myapp")          # 追加 INSTALLED_APPS（去重保序）
        assembly.add_middleware("myapp.middleware.My")  # 追加 MIDDLEWARE（保序）
        assembly.add_setting("MY_FEATURE_LIMIT", 10)    # 其余 Django settings
```

约束（Litestar 语义：**注册序即优先序，后写覆盖先写**，无插件间冲突检测）：

- `add_setting` 的 key 必须全大写；框架保留项（`SECRET_KEY`、`DEBUG`、`DATABASES` 等，
  见 `RESERVED_SETTING_KEYS`）不可覆盖——违例在贡献期立即报错（`ContributionConflictError`）。
- `contribute()` 中禁止访问 `django.conf.settings`（尚未 configure）与任何 IO。
- 插件间的贡献顺序依赖请在插件文档中声明（与 Litestar 相同的约定）。

### CLI 命令贡献

实现 `CLIPlugin` 面，直接在根 Typer 组上注册命令（Litestar `on_cli_init` 对应物）：

```python
from do_as_beginner.server.plugins import CLIPlugin
from typer import Typer

class MyPlugin(ServerPlugin, CLIPlugin):
    name = "my"

    def on_cli_init(self, cli: Typer) -> None:
        sub = Typer(help="myapp management")
        sub.command(name="sync")(sync_command)
        cli.add_typer(sub, name="myapp")   # 之后 `app myapp sync` 可用
```

### DI 注册

在 `setup()` 中向默认容器注册工厂/实例（与内置插件同一模式）：

```python
from do_as_beginner.server.depi import DI

def setup(self) -> None:
    DI.get_default_container().register(MyClient(...), key="my_client")
```

key 在容器内唯一（重复注册抛 `DuplicateDependencyError`）；消费方用
`Annotated[MyClient, NamedDependency("my_client")]` 注入。注册是惰性单例——解析发生在
首次 `get`/`aget`，因此 `setup()` 里不必 import Django models。

### Celery 任务贡献

```python
def contribute(self, assembly: AssemblyContext) -> None:
    assembly.add_celery_task_module("myapp.tasks")     # 合并进 CELERY_IMPORTS（去重保序）
    assembly.add_beat_entry("my_pulse", {              # 合并进 beat 调度（同名后写覆盖先写）
        "task": "myapp.tasks.pulse",
        "schedule": 30.0,
    })
```

beat 项最终在 `Scheduler.bootstrap`（任务导入后）与代码声明的 `@periodic_task` 及内部
ticks 合并；entry 名与代码声明冲突时报 `ContributionConflictError`。

### lifespan 贡献（异步/同步资源生命周期）

需要确定性建立/释放的资源，登记一个上下文管理器工厂：

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def _client_lifespan():
    client = await open_client()
    try:
        yield client
    finally:
        await client.aclose()

def contribute(self, assembly: AssemblyContext) -> None:
    assembly.add_lifespan(_client_lifespan)
```

工厂在 ASGI lifespan startup 按声明序建立、在 shutdown 逆序释放（AsyncExitStack 语义）。
这适合 Web 进程；`contribute`/`setup` 仍是同步的。

## 生命周期与 shutdown 语义

- 注册序即生命周期序；`shutdown()` 按 setup 的反序（LIFO）调用。
- shutdown 由框架统一托管：Web 进程在 ASGI `lifespan.shutdown`（uvicorn SIGTERM 下可靠触发），
  Celery worker 在 `worker_shutting_down`，CLI/dev 路径由 `atexit` 兜底。
- 只清理已成功 `setup()` 的插件（配对化）；单个插件 shutdown 抛错只记告警，不影响其余插件释放。
- 你的 `shutdown()` 应幂等、可安全二次调用。

## 错误速查

| 异常 | 触发 | 时机 |
|-|-|-|
| `DuplicatePluginError` | 同名插件重复注册 | 注册期 |
| `ContributionConflictError` | settings key 撞框架保留项；beat entry 撞代码声明项 | contribute 期 / bootstrap 合并时 |
| `PluginSetupError` | 插件 `setup()` 抛异常（原异常为 `__cause__`） | setup 期，启动中止 |
