from src.clients.jm import JmClient
from src.sources import SourcePlugin


class JmPlugin(SourcePlugin):
    id = "jm"
    name = "禁漫天堂"
    capabilities = ["search", "detail", "pages", "latest", "category", "leaderboard", "random"]
    categories = [{"value": v, "label": n} for v, n in
                  [("doujin", "同人"), ("single", "单本"), ("short", "短篇"), ("another", "其他")]]
    sorts = [{"value": v, "label": n} for v, n in
             [("new", "最新上架"), ("mv", "最多观看"), ("tf", "最多收藏"), ("mp", "最多指名")]]
    leaderboard_modes = [{"value": v, "label": n} for v, n in
                         [("day", "日榜"), ("week", "周榜"), ("month", "月榜"), ("total", "总榜")]]

    def __init__(self, store):
        super().__init__(store)
        self.client = JmClient()

    def browse(self, action, page=1, sort="", mode="day", name=""):
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
