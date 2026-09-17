# blobs — 文件内容存储

dab 内置的**内容寻址**文件内容存储层：文件内容存 PostgreSQL（`bytea`），以 sha256 为键自动
去重，引用计数管理生命周期，写入与业务记录**同事务强一致**（「业务记录提交 ⟺ 文件可见」）。

- 后端无关的 async 抽象层（`BlobStore` Protocol）+ 内置 `DatabaseBlobStore`（bytea 后端）
- 双轨 API：`BlobService` 服务门面（推荐，免 ORM）与 ORM 模型路径（需要与业务行同事务时）
- 删除即同事务删行 —— 没有后台 GC 任务

## 配置

```yaml
# config.yaml
blobs:
  backend: database        # MVP 仅 database（bytea）
  max_blob_bytes: 67108864 # 单文件上限，默认 64 MiB
  options: {}              # 未来后端的扩展选项
```

不写 `blobs:` 段时使用默认值。

## 服务路径（推荐）

经 DI 注入工厂（`BlobsPlugin` 已在 `PluginCore.setup()` 中注册）：

```python
from typing import Annotated

from do_as_beginner.blobs import BlobService, BlobServiceFactory
from do_as_beginner.server.di import NamedDependency


async def handler(
    blobs_factory: Annotated[BlobServiceFactory, NamedDependency("blob_service_factory")],
) -> GenericResponse:
    blobs = blobs_factory.create()
    ...
```

### 存取（去重幂等）

```python
info = await blobs.put(content)          # key = sha256(content)；同内容只存一行
data = await blobs.get(info.key)         # 全量读取；可加 max_size= 读守卫
meta = await blobs.info(info.key)        # 元数据（不加载内容）
await blobs.exists(info.key)             # -> bool（永不抛领域异常）
```

### 与业务对象关联（引用 + 引用计数）

```python
# 原子入口：存内容 + 建引用在一个事务内（服务路径强一致写法）
info, reference = await blobs.put_and_attach(content, obj=my_model_instance, field="attachment")

# 或分步：先存、后挂
info = await blobs.put(content)
reference = await blobs.attach(info.key, obj=my_model_instance, field="attachment")
```

- 同一 `(业务对象, field, blob)` 重复 `attach` 幂等返回既有引用，计数不变
- 同一 `field` 可挂多个不同 blob（多值集合语义）；「替换附件」= 先 `release` 旧引用再 `attach`

### 删除（唯一入口是引用）

```python
await blobs.release(reference)            # 引用行删除 + 计数 −1；计数归零时同事务删除 blob 行
await blobs.purge_references(obj)         # 删除某业务对象的全部引用（业务对象删除时必须调用）
await blobs.discard(key)                  # 仅删除无引用的孤儿 blob；仍有引用时返回 False 不动作
```

> 门面**不提供**按 key 无条件删除 —— 内容被多对象共享时，直接删行会破坏其他引用方。

## 模型路径（与业务行同事务）

需要在自己的事务里把文件与业务记录一起提交时（最强的一致性形态）：

```python
from django.contrib.contenttypes.models import ContentType
from django_async_backend.db.transaction import async_atomic
from do_as_beginner.blobs import Blob, BlobReference
from do_as_beginner.blobs.async_orm import async_manager


async with async_atomic():
    my_record = await MyModel.async_objects.acreate(...)
    blob = await Blob.acreate_from_content(content)          # 去重感知：命中即复用
    ctype = await async_manager(ContentType).aget(
        app_label=MyModel._meta.app_label, model=MyModel._meta.model_name
    )
    await BlobReference.acreate_tracked(                     # 建引用 + 同事务计数 +1
        blob=blob,
        content_type=ctype,
        object_id=my_record.pk,
        field="attachment",
    )
# 提交 ⟺ 文件可见；回滚 ⟺ blob、引用、计数全部消失
```

**注意**：模型路径的 ORM 读写必须走 `async_objects` / `async_save`（异步连接面），原生
`.objects.acreate()` 走同步连接、不在 `async_atomic` 事务内。

## 规则与边界（务必遵守）

1. **引用计数只经受支持入口变更**：写入 `acreate_tracked` / `attach`；删除
   `release` / `purge_references`。裸 ORM `acreate`（不计数）与 `adelete`（不减计数）
   会破坏「计数 == 引用行数」不变式，属**不受支持路径**。
2. **删除带引用的业务对象必须先 `purge_references(obj)`** —— 不要依赖
   `GenericRelation` 级联删除（级联绕过计数）。
3. `object_id` 为整型主键（BIGINT）；UUID/字符串主键的业务模型暂不支持。
4. 大小上限 `max_blob_bytes` 同时是内存防线：`get` 会把整个内容读进内存，大文件读取请传
   `max_size` 守卫。
5. 仅服务端读写；本模块不提供 HTTP 上传/下载端点。

## 异常

| 异常 | 触发 | 处理建议 |
|-|-|-|
| `BlobNotFoundError` | key 不存在；attach 时 blob 被并发释放 | 404 类语义 / 重新 put |
| `BlobValidationError`（含 `BlobTooLargeError`） | key 非法、obj 未保存/非整型主键、field 超长、内容超限 | 修正输入 |
| `BlobReferenceError` | 并发 release 丢失（引用行已消失） | 可重试：重读后重试 |
| `BlobIntegrityError` | 计数与引用行数不一致（不变式被破坏） | **缺陷上报**，不可重试 |
| `BlobBackendError` | 底层 DB 错误包装 | 记录后上抛 |

基类 `BlobStoreError` 可兜底捕获全部存储异常。

## 测试

单元测试随 `pytest` 直接运行；一致性/并发验证需要真实 PostgreSQL：

```bash
pytest                                          # SQLite 单测（PG 集成测试自动跳过）
DAB_TEST_PG_DSN=postgres://user:pass@host:5432/dbname pytest   # 全量（含 PG 集成）
```
