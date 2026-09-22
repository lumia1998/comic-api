import io
import time
from types import SimpleNamespace
from PIL import Image
from src.sources import SourcePlugin
from src.errors import ComicApiError


class DemoPlugin(SourcePlugin):
    id = "demo"
    name = "测试图源"
    capabilities = ["search", "detail", "pages", "latest", "login"]
    login_fields = [{"name": "account", "label": "账号", "type": "text"}, {"name": "password", "label": "密码", "type": "password"}]

    def __init__(self, store):
        super().__init__(store)
        data = io.BytesIO()
        Image.new("RGB", (120, 180), "#a6c78c").save(data, "PNG")
        self.picture = data.getvalue()
        self.client = SimpleNamespace(ua="test", request=self.request)
        self.fail = False
        self.delay = 0

    def request(self, *args, **kwargs):
        time.sleep(self.delay)
        if self.fail:
            raise ComicApiError("图源暂时故障", 502, "upstream_error", self.id)
        return SimpleNamespace(status_code=200, content=self.picture)

    def search(self, keyword, page=1):
        if keyword == "fail":
            raise ComicApiError("需要登录", 401, "login_required", self.id)
        if keyword == "empty":
            return []
        return [self.detail("same-id")]

    def detail(self, comic_id):
        return {"source": self.id, "id": comic_id, "title": "春日书信", "author": "测试作者", "description": "用于验证书库、阅读和后台下载。",
                "cover": "/api/image/proxy?source=demo&url=https%3A%2F%2Fdemo.invalid%2Fcover.png",
                "chapters": [{"id": str(i), "name": f"第 {i} 章"} for i in range(1,4)]}

    def pages(self, *args):
        return [f"https://demo.invalid/{i}.png" for i in range(3)]

    def browse(self, *args, **kwargs):
        return self.search("")

    def login(self, values):
        self.store.save_account(self.id, dict(values, token="test-token"))

    def logout(self):
        self.store.save_account(self.id, {})

    def account_status(self):
        saved = self.store.account(self.id) or {}
        return {"configured": bool(saved), "authenticated": bool(saved.get("token"))}
