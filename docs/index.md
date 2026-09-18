# Do as Beginner

`do-as-beginner`（dab）是一个 async-first 的 Web 框架，封装 Django：Django settings
在运行时由 Pydantic 配置（`config.yaml`）程序化构建（没有 `settings.py`），默认数据库
为 PostgreSQL（`django-async-backend` + psycopg 连接池），HTTP 层基于控制器，处理器
支持同步/异步写法。

```{toctree}
:maxdepth: 2

dev-guides/index
```
