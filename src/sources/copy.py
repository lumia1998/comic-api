"""Copy API adapter. Protocol reference: deretame/Breeze-plugin-copyComic.

This is a native Python adapter, not an embedded Breeze JavaScript runtime.
"""
import os
import threading
import time
from urllib.parse import quote

from src.clients.base import BaseClient
from src.errors import ComicApiError
from src.sources import SourcePlugin


class CopyPlugin(SourcePlugin):
    id = "copy"
    name = "拷贝漫画"
    settings_fields = [{"name": "api_base", "label": "服务器地址", "type": "url",
                        "description": "拷贝漫画 API 地址，须包含 /api/v3；留空恢复部署默认地址。"}]
    capabilities = ["search", "detail", "pages", "latest", "category", "leaderboard", "random"]
    categories = [{"value": v, "label": n} for v, n in
                  [("", "全部"), ("maoxian", "冒险"), ("qihuan", "奇幻"), ("aiqing", "爱情"),
                   ("kehuan", "科幻"), ("shenghuo", "生活"), ("rexue", "热血"), ("xuanyi", "悬疑")]]
    sorts = [{"value": "-datetime_updated", "label": "最新更新"}, {"value": "-popular", "label": "热度最高"}]
    leaderboard_modes = [{"value": v, "label": n} for v, n in
                         [("day", "日榜"), ("week", "周榜"), ("month", "月榜"), ("total", "总榜")]]

    def __init__(self, store):
        super().__init__(store)
        self.client = BaseClient()
        self.default_base = os.environ.get("COPY_API_BASE", "https://api.copy3000.com/api/v3").rstrip("/")
        self.base = store.source_settings(self.id).get("api_base") or self.default_base
        self._chapter_lock = threading.Lock()
        self._chapter_clock = {"next": 0.0}
        self._page_cache = {}

    def settings(self):
        return {"api_base": self.base}

    def save_settings(self, values):
        from urllib.parse import urlparse
        if set(values) - {"api_base"}:
            raise ComicApiError("未知图源设置", 422, "invalid_request", self.id)
        value = values.get("api_base", "").strip().rstrip("/") or self.default_base
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ComicApiError("请输入不含凭据、查询参数的 HTTPS API 地址", 422, "invalid_request", self.id)
        self.store.save_source_settings(self.id, {"api_base": value})
        # Replace the adapter for subsequent calls; already-running calls keep their old instance.
        replacement = type(self)(self.store)
        replacement.client = self.client
        replacement._chapter_lock = self._chapter_lock
        replacement._chapter_clock = self._chapter_clock
        return replacement

    def _get(self, path, **params):
        headers = {"Accept": "application/json", "version": "2025.05.09", "platform": "1",
                   "Origin": "https://2025copy.com", "region": "0", "webp": "0"}
        response = self.client.request("GET", self.base + "/" + path, params=params, headers=headers)
        status = response.status_code
        if status >= 400:
            raise ComicApiError(f"拷贝漫画返回 HTTP {status}", status if status in (401,403,404,429) else 502,
                                {401: "login_required", 403: "upstream_forbidden", 404: "not_found", 429: "rate_limited"}.get(status, "upstream_error"), self.id)
        try:
            payload = response.json()
            code = int(payload.get("code", 0))
            if code != 200:
                # Surface upstream's own explanation (e.g. code 210 temporary IP restriction).
                reason = str(payload.get("message") or "").strip()[:200]
                message = f"拷贝漫画拒绝请求：{reason}" if reason else "拷贝漫画接口拒绝请求"
                raise ComicApiError(message, code if code in (401,403,404,429) else 502, "upstream_error", self.id)
            result = payload["results"]
            if not isinstance(result, dict):
                raise ValueError("results is not an object")
            return result
        except (KeyError, ValueError, TypeError) as exc:
            raise ComicApiError("拷贝漫画响应格式已变化", 502, "invalid_response", self.id) from exc

    def _comic(self, item):
        return {"id": str(item["path_word"]), "source": self.id, "title": item.get("name", ""),
                "cover": item.get("cover", ""), "description": item.get("brief", ""),
                "author": " / ".join(author.get("name", "") for author in item.get("author", []))}

    def _items(self, data):
        items = []
        for row in data.get("list", []):
            item = row.get("comic") or row.get("book") or row
            if item.get("path_word"):
                items.append(self._comic(item))
        return items

    def search(self, keyword, page=1, sort=""):
        # 上游搜索接口不接受排序参数；排序由浏览接口提供。
        return self._items(self._get("search/comic", q=keyword, q_type="", limit=20, offset=(page-1)*20, platform=1))

    def detail(self, comic_id):
        cid = quote(comic_id, safe="")
        data = self._get(f"comic2/{cid}", platform=1)
        comic = data.get("comic") or {}
        if not comic.get("path_word"):
            raise ComicApiError("漫画不存在", 404, "not_found", self.id)
        result = self._comic(comic)
        groups = data.get("groups") or comic.get("groups") or {}
        if isinstance(groups, dict):
            groups = list(groups.values())
        chapters, seen = [], set()
        for group in groups:
            name = group.get("path_word")
            if not name:
                continue
            offset = 0
            while True:
                batch = self._get(f"comic/{cid}/group/{quote(name, safe='')}/chapters", limit=500, offset=offset)
                rows = batch.get("list", [])
                added = 0
                for row in rows:
                    chapter_id = str(row.get("uuid", ""))
                    if not chapter_id or chapter_id in seen:
                        continue
                    seen.add(chapter_id)
                    added += 1
                    chapters.append({"id": chapter_id, "name": f"{group.get('name', '')} {row.get('name', '')}".strip(), "order": len(chapters)+1})
                offset += len(rows)
                if offset >= int(batch.get("total", offset)) or not rows:
                    break
                if not added:
                    raise ComicApiError("拷贝漫画章节分页重复，已停止加载", 502, "invalid_response", self.id)
        return dict(result, chapters=chapters)

    def pages(self, comic_id, chapter_id):
        # Match the reference plugin's 10 chapter requests/minute; cache successful responses.
        key = (comic_id, chapter_id)
        with self._chapter_lock:
            cached = self._page_cache.get(key)
            if cached and time.monotonic() - cached[0] < 600:
                return list(cached[1])
            time.sleep(max(0, self._chapter_clock["next"] - time.monotonic()))
            self._chapter_clock["next"] = time.monotonic() + 6
            cid, chapter = quote(comic_id, safe=""), quote(chapter_id, safe="")
            try:
                data = self._get(f"comic/{cid}/chapter2/{chapter}", platform=1)
            except ComicApiError as exc:
                if exc.status_code != 404:
                    raise
                data = self._get(f"comic/{cid}/chapter/{chapter}", platform=1)
            content = data.get("chapter", {})
            urls = [item.get("url", "") for item in content.get("contents", [])]
            words = content.get("words", [])
            if len(words) == len(urls):
                try:
                    urls = [url for _, _, url in sorted((float(word), i, url) for i, (word, url) in enumerate(zip(words, urls)))]
                except (ValueError, TypeError):
                    raise ComicApiError("章节页序格式错误", 502, "invalid_response", self.id)
            urls = [url for url in urls if url]
            if len(self._page_cache) >= 128:
                self._page_cache.pop(next(iter(self._page_cache)))
            self._page_cache[key] = (time.monotonic(), urls)
            return urls

    def browse(self, action, page=1, sort="", mode="day", name=""):
        params = {"limit": 20, "offset": (page-1)*20, "platform": 3}
        if action == "random":
            data = self._get("recs", pos="3200102", **params)
        elif action == "leaderboard":
            data = self._get("ranks", type=1, date_type=mode, audience_type="male", **params)
        elif action == "latest":
            try:
                data = self._get("update/newest", **params)
            except ComicApiError as exc:
                if exc.status_code != 404:
                    raise
                data = self._get("comics", ordering="-datetime_updated", **params)
        else:
            data = self._get("comics", theme=name, ordering=sort or "-datetime_updated", free_type=1, **params)
        return self._items(data)


create_plugin = CopyPlugin
