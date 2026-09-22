from src.clients.bika import BikaClient
from src.sources import SourcePlugin


class BikaPlugin(SourcePlugin):
    id = "bika"
    name = "哔咔漫画"
    capabilities = ["search", "detail", "pages", "latest", "category", "leaderboard", "random", "login"]
    login_fields = [{"name": "account", "label": "账号", "type": "text"},
                    {"name": "password", "label": "密码", "type": "password"}]
    categories = [{"value": name, "label": name} for name in
                  ["嗶咔漢化", "同人", "全彩", "少女漫畫", "耽美", "妹子", "治癒", "都市", "冒險"]]
    sorts = [{"value": v, "label": n} for v, n in
             [("dd", "最新上架"), ("ld", "最多喜欢"), ("vd", "最多观看"), ("da", "最旧上架")]]
    leaderboard_modes = [{"value": v, "label": n} for v, n in [("day", "日榜"), ("week", "周榜"), ("month", "月榜")]]

    def __init__(self, store):
        super().__init__(store)
        self.client = BikaClient(store=store)

    def account_status(self):
        return {"authenticated": bool(self.client.authorization), "configured": self.client._credentials_available()}

    def login(self, values):
        self.client.login(values.get("account", ""), values.get("password", ""))

    def logout(self):
        with self.client._auth_lock:
            self.store.save_account(self.id, {})
            self.client.authorization = self.client._account = self.client._password = ""

    def browse(self, action, page=1, sort="", mode="day", name=""):
        self.client.ensure_authenticated()
        if action == "random":
            return self.client.get_random()
        if action == "leaderboard":
            return self.client.get_leaderboard(mode)[(page - 1) * 20:page * 20]
        if action == "latest":
            return self.client.get_latest(page, sort or "dd")
        return self.client.get_category_comics(name, page, sort or "dd")


create_plugin = BikaPlugin
