# 插件编写指南

面向应用开发者的 do-as-beginner（dab）插件公开 API。读完本页即可编写并注册一个
插件，无需阅读框架源码。

## 概览

插件是**继承**若干**能力面（facet）协议**的普通 Python 类（Litestar PluginProtocol
模式）。框架在 setup 期用 `isinstance` 识别插件实现了哪些能力面，按注册序调用对应
钩子；全部钩子都是**同步**的——异步资源的生命周期通过插件上的 `__lifespan__`
上下文管理器表达，不设 async 钩子。

| 能力面（`do_as_beginner.server.core`） | 钩子 | 调用时机 | 典型用途 |
|-|-|-|-|
| `PluginProtocol` | —（基面，仅标记） | — | 所有插件的根 |
| `AppPluginProtocol` | `on_app_init(container)` | `django.setup()` 之后，注册序 | 向 DI 容器注册依赖 |
| `CLIPluginProtocol` | `on_cli_init(group)` | 同一 setup 期，注册序 | 向根 Typer 组注入命令 |

另有可选属性/方法：

- `name: str`——插件身份（注册期校验唯一性）；省略时用类名。
- `__lifespan__`——`@asynccontextmanager` 装饰的异步上下文管理器方法；setup 期被
  收集，在 ASGI lifespan startup 按序建立、shutdown 逆序释放。

## 编写与注册插件

继承需要的协议面，把**实例**传给组合根 `AppConfigCore`（`do_as_beginner.server.setup`，
varargs 显式注册——没有自动发现）：

```python
from do_as_beginner.server.core import AppPluginProtocol, CLIPluginProtocol
from do_as_beginner.server.setup import AppConfigCore
from do_as_beginner.server.depi import Container
from typer import Typer

class MyPlugin(AppPluginProtocol, CLIPluginProtocol):
    name = "my"

    def on_app_init(self, container: Container) -> None:
        ...  # 见下文 DI 注册

    def on_cli_init(self, group: Typer) -> None:
        ...  # 见下文 CLI 命令贡献

core = AppConfigCore(MyPlugin())
core.setup()   # settings.configure + django.setup + 逐插件钩子（注册序）
```

`setup()` 的执行序：构建 Django/Celery settings 清单 → 一次 `settings.configure()` +
`django.setup()` → 按注册序对每个插件调用 `on_app_init` / `on_cli_init`，并收集
`__lifespan__`。插件构造发生在**注册时**（调用方 `MyPlugin()`），构造约定为无参或
自行读取 `AppConfig.load()`。

## 内置插件

四个内置插件在 `do_as_beginner.server.plugins`，构造**无参**（各自在钩子里读
`AppConfig.load()`）：

| 插件 | 面 | 作用 |
|-|-|-|
| `BlobsPlugin` | App | 注册 `blob_service_factory`（读 `config.blobs`） |
| `RedisPlugin` | App | 注册 `redis_factory`（读 `config.redis`） |
| `QdrantPlugin` | App | 注册 `qdrant_client`（读 `config.qdrant`） |
| `OtelPlugin` | App + `__lifespan__` | OpenTelemetry 插桩；provider 释放挂在自身 `shutdown()`（内部实现），由 `__lifespan__` 驱动 |

内置插件与用户插件**同一条注册路径**——显式传入 `AppConfigCore(...)`：

```python
from do_as_beginner.server.plugins import BlobsPlugin, OtelPlugin, QdrantPlugin, RedisPlugin

core = AppConfigCore(BlobsPlugin(), OtelPlugin(), QdrantPlugin(), RedisPlugin(), MyPlugin())
```

> 注意：当前 `app` 内置入口（`do_as_beginner.asgi`）构造 `AppConfigCore()` 时**不传**
> 任何插件。需要内置插件能力时，请在自己的 ASGI 工厂 / 入口中按上式显式组合。

## 贡献能力面

### DI 注册（`on_app_init`）

向传入的容器注册工厂/实例（与内置插件同一模式）：

```python
def on_app_init(self, container: Container) -> None:
    container.register(MyClient(...), key="my_client")
```

key 在容器内唯一（重复注册抛 `DuplicateDependencyError`）；消费方用
`Annotated[MyClient, NamedDependency("my_client")]` 注入。注册是惰性单例——解析发生在
首次 `get`/`aget`，因此钩子里不必 import Django models。`AppPluginProtocol` 与
`CLIPluginProtocol` 的钩子在同一个 setup 循环里按插件逐个调用，先注册的插件先执行。

### CLI 命令贡献（`on_cli_init`）

直接在根 Typer 组上注册命令或子组：

```python
def on_cli_init(self, group: Typer) -> None:
    sub = Typer(help="myapp management")
    sub.command(name="sync")(sync_command)
    group.add_typer(sub, name="myapp")   # 之后 `app myapp sync` 可用
```

### 异步资源生命周期（`__lifespan__`）

需要确定性建立/释放的资源，在插件上定义 `__lifespan__`：

```python
from contextlib import asynccontextmanager

class MyPlugin(AppPluginProtocol):

    def on_app_init(self, container: Container) -> None: ...

    @asynccontextmanager
    async def __lifespan__(self):
        client = await open_client()
        try:
            yield client
        finally:
            await client.aclose()
```

收集在 setup 期完成；ASGI lifespan startup 按声明序建立、shutdown 逆序释放
（AsyncExitStack 语义）。只在 Web 进程生效——Celery 主进程没有 lifespan，
`__lifespan__` 不会运行（已知限制）。

## 生命周期语义

- 注册序即执行序；`__lifespan__` 的释放与建立严格逆序（LIFO）。
- 没有 sync `shutdown()` 钩子、没有 shutdown 管线：进程内同步资源的释放请放进
  `__lifespan__`（框架统一经 ASGI lifespan 托管）。
- 单个插件钩子抛错 → 启动中止，包装为 `PluginSetupError`（原异常为 `__cause__`）。

## 错误速查

| 异常 | 触发 | 时机 |
|-|-|-|
| `DuplicatePluginError` | 同名插件重复注册 | `AppConfigCore(...)` 构造期 |
| `PluginSetupError` | 插件 `on_app_init`/`on_cli_init` 抛异常（原异常为 `__cause__`） | setup 期，启动中止 |
| `ContributionConflictError` | 装配清单撞框架保留 settings key（`RESERVED_SETTING_KEYS`） | 装配期（框架内部） |
| `DuplicateDependencyError` | 同一 DI key 重复注册 | `container.register` |
