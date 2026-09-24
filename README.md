# Comic API

Python / FastAPI 多图源漫画 WebUI。内置禁漫、哔咔、拷贝漫画；前端按插件能力生成浏览入口与登录表单。

右上角「图源管理」显示图源列表，每行进入独立「设置」。有登录能力的图源提供「登录凭证」子页面，再填写账号与密码；拷贝漫画提供服务器地址设置，保存到 SQL，优先于环境变量，新请求立即生效。正在执行的请求继续使用原地址；留空可恢复部署默认地址。服务器地址仅接受不含嵌入凭据的 HTTPS URL，只应填写可信服务器。

## 部署

```bash
cp .env.example .env
docker compose up -d --build
```

访问 http://localhost:34587 。哔咔账号可以在页面绑定，也可以在首次启动前填入 `.env`。禁漫与拷贝当前使用游客接口，不显示账号登录。

本地运行：

```bash
pip install -r requirements.txt
python main.py
```

本地端口 8699。只运行一个服务进程 / 一个 Uvicorn worker：下载队列与图源限流器在进程内管理，不支持多个实例共享数据库。当前没有站点用户认证；图源账号、书库与下载属于服务实例，**不要直接暴露到公网**，需要时在反向代理增加访问认证。

## 数据与功能

- **混合搜索**：各图源结果统一展示并标注来源，按标题完全匹配、包含关键词、字符相似度排序；忽略大小写、全半角与标点差异。同名的不同图源版本保留独立入口。排序范围是本次返回的结果（聚合搜索为各源首页），不是全站全部漫画，也不包含语义理解或简繁转换。

- **图片代理**：封面与章节图片统一经 `/api/image/proxy` 中转，浏览器不直接连图源 CDN；代理拒绝非公网地址（SSRF 防护），成功响应按源+URL 缓存到磁盘（最多保留约 2000 张）。
- **图源账号**：SQLite 按图源隔离，账号与 Token 使用 AES-GCM 加密。首次启动自动导入原 `.bika_token` / `.bika_credentials.json`，之后以 SQL 为准；退出登录不会重新导入。旧文件不会自动删除，确认迁移成功后可自行清理其中的明文凭据。
- **书库**：收藏、分类、移除、缓存详情与手动检查章节更新；页面支持按分类与标题/作者关键词筛选。同一本漫画的不同图源记录互不覆盖。尚未实现后台定时追更。
- **下载任务**：排队、图片进度、打包状态、取消、失败重试、取回 PDF、删除任务及文件；详情页可一键把全部章节加入队列（已有同章节任务自动去重）。单任务执行，最多 100 个排队任务。重启后未结束的任务标记为中断，需手动重试；重试从头开始，不是断点续传。取消会等待已开始的网络请求或打包操作退出并清理文件。
- **阅读进度**：仅保存在浏览器 localStorage，按图源、漫画和章节隔离；支持续读、滚动/翻页模式。不会写入服务器 SQL，也不跨浏览器同步。清除站点数据或更换访问域名/端口会影响可见进度。
- **明确错误**：接口区分登录失效、限流、网络超时、上游错误与参数错误。聚合搜索保留可用图源结果，并单独报告失败源，不把失败伪装成空结果。
- **并发边界**：每源最多 2 个业务调用；每客户端最多 4 个网络请求；阅读图片最多 8 个并发处理；PDF 默认最多 4 个图片下载。同步请求在线程执行，取消等待不会提前释放仍在工作的线程配额。拷贝章节请求间隔至少 6 秒，并缓存成功结果 10 分钟。

默认数据目录为 `./data`，可用 `DATA_DIR` 修改。Docker 已挂载 `./data:/app/data`：

| 路径 | 内容 |
| --- | --- |
| `comic.sqlite` | 图源凭据密文、书库、下载记录 |
| `credentials.key` | 凭据加密密钥，必须保密并与数据库一起备份 |
| `downloads/` | 已生成的 PDF |
| `plugins/` | 自定义可信 Python 图源 |

备份建议先停止服务再复制整个数据目录，避免遗漏 SQLite WAL。密钥丢失后无法解密旧账号。加密不防御可同时读取数据库和密钥的主机管理员。PDF 密码显示在任务卡上，沿用确定性六位密码，主要用于阅读流程而非强机密保护。

## 插件扩展

内置插件位于 `src/sources/`；自定义插件放到 `DATA_DIR/plugins/*.py`，重启自动发现。每个模块导出 `create_plugin(store)`，返回 `SourcePlugin` 子类实例，提供唯一 `id`、`name` 与 `capabilities`。插件是**可信的服务器 Python 代码**，没有沙箱；不要安装不可信文件，也不直接兼容 Breeze JavaScript 插件或 Suwayomi APK。

核心接口：

- `search(keyword, page)`：漫画列表，每项含 `id/title/cover/author`。
- `detail(comic_id)`：漫画详情及 `chapters: [{id, name, order}]`。
- `pages(comic_id, chapter_id)`：有序图片 URL 列表。
- `client.request(...)`：图片请求客户端；可选 `transform_image(data, chapter_id, url)` 解码图片。
- 可选 `browse(action, **filters)`、`login(values)`、`logout()`、`account_status()`；通过 `categories/sorts/leaderboard_modes/login_fields` 描述界面。
- 可选 `settings_fields`、`settings()` 描述非敏感设置；`save_settings(values)` 持久化并返回替换用的新插件实例。不要把密码或 Token 放进设置清单，应使用登录凭证接口。

参考 `src/sources/bika.py` 的账号插件和 `src/sources/copy.py` 的游客插件。账号可使用 `store.save_account(plugin.id, data)` 保存，加密由存储层处理。

拷贝适配器参考 [Breeze-plugin-copyComic](https://github.com/deretame/Breeze-plugin-copyComic) 的 API 协议，在 Python 中实现搜索、章节分组分页、图片顺序、推荐与排行榜。`COPY_API_BASE` 可修改 API 地址；上游域名、限流与接口变化可能导致服务不可用。

## API

完整参数见 `/docs`。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/sources` | 插件能力与账号状态，不返回凭据 |
| POST / DELETE | `/api/sources/{source}/login` / `/api/sources/{source}/account` | 登录 / 退出 |
| GET | `/api/search?keyword=&source=&page=1` | 搜索；省略 source 聚合各源首页 |
| GET | `/api/comic/{source}/{comic_id}` | 详情 |
| GET | `/api/chapter/{source}/{comic_id}/{chapter_id}` | 图片代理列表 |
| GET | `/api/{source}/{action}` | latest / category / leaderboard / random，按能力开放 |
| GET | `/api/library` | 书库 |
| PUT / PATCH / DELETE | `/api/library/{source}/{comic_id}` | 收藏 / 改分类 / 移除 |
| POST | `/api/library/{source}/{comic_id}/refresh` | 检查更新 |
| GET / POST | `/api/downloads` | 列表 / 创建下载 |
| GET / DELETE | `/api/downloads/{task_id}` | 状态 / 删除 |
| POST | `/api/downloads/{task_id}/cancel` 或 `/retry` | 取消 / 重试 |
| GET | `/api/downloads/{task_id}/file` | 下载 PDF |

旧 `/api/bika/login` 保留。旧同步 `/api/download/{source}/{comic_id}/{chapter_id}` 会创建任务并等待，不建议用于长连接；请改用任务 API。下载并发和 PDF 密码由服务统一管理，不再接受调用者覆盖。

## 项目结构

```
main.py                  FastAPI 路由与应用装配
src/config.py            JM / Bika 上游端点与密钥
src/storage.py           SQLite 存储与 AES-GCM 凭据加密
src/sources/             图源插件抽象与内置插件（bika / jm / copy）
src/clients/             上游协议客户端（签名、解密、HTTP 伪装）
src/services/aggregator.py   插件调度、聚合搜索、标题排序
src/services/image_proxy.py  图片代理：SSRF 防护、并发上限、磁盘缓存
src/services/pdf.py          章节图片并发下载与自适应压缩 PDF
src/services/downloads.py    下载任务队列与生命周期
src/services/images.py       JM 图片反切割
src/web/                 原生 JS 单页界面
tests/                   pytest，无需真实账号
scripts/                 Playwright 界面走查与布局断言（开发用）
```

## 测试

```bash
pip install pytest httpx
python -m pytest tests -q
```

测试使用临时数据库和模拟图源，不需要实际账号。`tests.demo_server` 提供离线 WebUI 验证数据，不用于生产部署。

## License

MIT
