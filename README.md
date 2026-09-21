# Comic API

多源漫画聚合搜索与下载服务，整合禁漫天堂 (JmComic) 和哔咔 (Bika) 两大平台。

## 功能特性

- **多源聚合搜索** - 同时查询禁漫和哔咔，智能匹配最佳结果
- **漫画详情** - 获取章节列表、作者、封面等信息
- **章节图片获取** - 支持禁漫图片解密
- **PDF下载** - 自适应压缩 + AES-256加密
- **随机推荐** - 发现新漫画
- **排行榜** - 日/周/月榜单
- **分类筛选** - 按类别浏览
- **最近更新** - 查看最新上架

## 快速开始

### Docker 部署 (推荐)

复制环境变量示例并填写哔咔账号：

```bash
cp .env.example .env
```

`.env`：

```dotenv
BIKA_ACCOUNT=你的哔咔邮箱
BIKA_PASSWORD=你的哔咔密码
```

启动服务：

```bash
docker compose up -d --build
```

服务启动后访问: http://localhost:34587

### 手动部署

```bash
cp .env.example .env
pip install -r requirements.txt
python main.py
```

服务默认监听: http://127.0.0.1:8699

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/search?keyword=` | 聚合搜索 |
| GET | `/api/comic/{source}/{id}` | 漫画详情 |
| GET | `/api/chapter/{source}/{comic_id}/{chapter_id}` | 章节图片 |
| POST | `/api/bika/login` | 哔咔登录 |
| GET | `/api/download/{source}/{comic_id}/{chapter_id}` | 下载PDF |
| GET | `/api/{source}/random` | 随机推荐 |
| GET | `/api/{source}/leaderboard?mode=` | 排行榜 |
| GET | `/api/{source}/latest?page=` | 最近更新 |
| GET | `/api/{source}/category?name=&sort=` | 分类筛选 |

**source 参数**: `jm` (禁漫) / `bika` (哔咔)

## 配置

推荐在 `.env` 中设置 `BIKA_ACCOUNT` 和 `BIKA_PASSWORD`。服务优先加载持久化 Token；Token 不存在或失效时，会使用账号密码自动登录并把新 Token 保存到数据目录。

也可以不配置 `.env`，直接通过 WebUI 或接口手动登录绑定账号。手动登录成功后，账号密码会明文保存到数据目录，供容器重启和 Token 失效后自动重新登录：

```bash
curl -X POST http://localhost:34587/api/bika/login \
  -H "Content-Type: application/json" \
  -d '{"account":"邮箱","password":"密码"}'
```

## Docker 数据持久化

哔咔登录 Token 自动保存在宿主机的 `./data/.bika_token`，账号密码保存在 `./data/.bika_credentials.json`。写入使用原子替换，容器重启或重建后仍可读取。若 Token 因其他设备登录而失效，服务会使用本地凭据自动重新登录并重试原请求一次。

禁漫没有账号登录流程。它的 JWT 由接口动态下发；JWT 返回 401/403 时，服务会清理旧会话并以无 JWT 状态重试一次。

`.bika_credentials.json` 是明文凭据文件，请确保 `./data` 目录权限受控。请勿提交 `.env` 或 `data/` 目录，它们已经包含在 `.gitignore` 和 `.dockerignore` 中。

## License

MIT
