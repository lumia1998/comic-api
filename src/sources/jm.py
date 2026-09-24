from src.clients.jm import JmClient
from src.sources import SourcePlugin


class JmPlugin(SourcePlugin):
    id = "jm"
    name = "禁漫天堂"
    capabilities = ["search", "detail", "pages", "latest", "category", "leaderboard", "random", "login"]
    login_fields = [{"name": "account", "label": "账号", "type": "text"},
                    {"name": "password", "label": "密码", "type": "password"}]
    categories = [{"value": v, "label": n} for v, n in
                  [("doujin", "同人"), ("single", "单本"), ("short", "短篇"), ("another", "其他")]]
    sorts = [{"value": v, "label": n} for v, n in
             [("new", "最新上架"), ("mv", "最多观看"), ("tf", "最多收藏"), ("mp", "最多指名")]]
    # 上游 mv_t（日榜）长期返回空数据，不展示该选项；默认落在周榜。
    leaderboard_modes = [{"value": v, "label": n} for v, n in
                         [("week", "周榜"), ("month", "月榜"), ("total", "总榜")]]

    def __init__(self, store):
        super().__init__(store)
        self.client = JmClient(store=store)

    def account_status(self):
        return {"authenticated": bool(self.client.jwt_token),
                "configured": self.client._credentials_available()}

    def login(self, values):
        self.client.login(values.get("account", ""), values.get("password", ""))

    def logout(self):
        with self.client._auth_lock:
            self.store.save_account(self.id, {})
            self.client.jwt_token = self.client._account = self.client._password = ""

    def browse(self, action, page=1, sort="", mode="week", name=""):
        if action == "random":
            return self.client.get_recommend()
        if action == "leaderboard":
            return self.client.get_leaderboard(mode, page)
        if action == "latest":
            return self.client.get_latest(page)
        return self.client.get_category_comics(name, page, sort or "new")

    def transform_image(self, data, chapter_id, url):
        from src.services.images import descramble_jm_image
        return descramble_jm_image(data, chapter_id, url) if chapter_id else data


create_plugin = JmPlugin
