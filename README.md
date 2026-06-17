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

```bash
docker compose up -d
```

服务启动后访问: http://localhost:34587

### 手动部署

```bash
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

哔咔功能需要先登录绑定账号：

```bash
curl -X POST http://localhost:34587/api/bika/login \
  -H "Content-Type: application/json" \
  -d '{"account":"邮箱","password":"密码"}'
```

## Docker 数据持久化

哔咔登录 Token 自动保存在 `./data/.bika_token`，重启服务后无需重复登录。

## License

MIT
