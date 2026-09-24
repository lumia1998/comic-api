"""Copy API adapter. Protocol reference: deretame/Breeze-plugin-copyComic.

This is a native Python adapter, not an embedded Breeze JavaScript runtime.
"""
import os
import threading
import time
from urllib.parse import quote, urlparse

from src.clients.base import BaseClient
from src.errors import ComicApiError
from src.sources import SourcePlugin

# 线路域名映射参考 Breeze-plugin-copyComic 的 API_DOMAIN_BASE_MAP。
API_DOMAIN_BASE_MAP = {
    "国际服": "https://api.mangacopy.com/api/v3",
    "国际服1": "https://api.copy2000.online/api/v3",
    "国际服2": "https://api.copy3000.com/api/v3",
    "大陆专线1": "https://mapi.copy20.com/api/v3",
    "大陆专线2": "https://mapi.copy2000.site/api/v3",
    "大陆专线3": "https://api.2025copy.com/api/v3",
    "大陆专线新站": "https://api.2026copy.com/api/v3",
    "热辣漫画线路1": "https://mapi.hotmangasd.com/api/v3",
    "热辣漫画线路2": "https://api.manga2025.com/api/v3",
    "热辣漫画线路3": "https://mapi.hotmangasf.com/api/v3",
    "热辣漫画线路4": "https://mapi.hotmangasg.com/api/v3",
    "热辣漫画线路5": "https://mapi.elfgjfghkk.club/api/v3",
    "热辣漫画线路6": "https://mapi.fgjfghkk.club/api/v3",
    "热辣漫画线路7": "https://mapi.fgjfghkkcenter.club/api/v3",
}
CUSTOM_DOMAIN = "自定义"
DEFAULT_API_DOMAIN = "国际服2"

# 参考插件的 api.platform 选项：会放进请求头，查询参数仍按各接口固定值。
PLATFORM_OPTIONS = [{"value": v, "label": n} for v, n in
                    [("1", "1（默认）"), ("2", "2"), ("3", "3"), ("4", "4"), ("5", "5"),
                     ("", "无"), (" ", "空格")]]
DEFAULT_PLATFORM = "1"

APP_FALLBACK_HEADERS = {
    "Accept": "application/json",
    "version": "2025.05.09",
    "Origin": "https://2025copy.com",
    "region": "0",
    "webp": "0",
    "platform": "1",
}


def _valid_api_base(value):
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.hostname \
        and not (parsed.username or parsed.password or parsed.query or parsed.fragment) \
        and parsed.path.startswith("/api/v3")


def _is_hot_manga_base(api_base):
    host = (urlparse(api_base).hostname or "").lower()
    return "hotmanga" in host or host == "api.manga2025.com" or "fgjfghkk" in host


def _is_anti_piracy_message(message):
    text = message.lower()
    return any(key in text for key in
               ("破解", "正版", "请到官网", "請到官網", "download", "更新最新app"))


class CopyPlugin(SourcePlugin):
    id = "copy"
    name = "拷贝漫画"
    settings_fields = [
        {"name": "api_domain", "label": "接口域名", "type": "select",
         "description": "切换拷贝漫画接口线路，连接失败时可尝试更换。",
         "options": [{"value": v, "label": v} for v in [*API_DOMAIN_BASE_MAP, CUSTOM_DOMAIN]]},
        {"name": "api_base", "label": "自定义服务器地址", "type": "url",
         "description": "接口域名选择“自定义”时生效，须包含 /api/v3；留空恢复默认线路。"},
        {"name": "platform", "label": "platform", "type": "select",
         "description": "请求头 platform 值，部分线路需要特定值才能访问。",
         "options": PLATFORM_OPTIONS},
    ]
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
        self.default_base = os.environ.get("COPY_API_BASE", API_DOMAIN_BASE_MAP[DEFAULT_API_DOMAIN]).rstrip("/")
        saved = store.source_settings(self.id)
        self.domain = self._resolve_domain(saved)
        self.base = self._resolve_base(saved)
        self.platform = self._resolve_platform(saved)
        self._chapter_lock = threading.Lock()
        self._chapter_clock = {"next": 0.0}
        self._page_cache = {}

    def _resolve_domain(self, saved):
        domain = saved.get("api_domain")
        if domain in API_DOMAIN_BASE_MAP or domain == CUSTOM_DOMAIN:
            return domain
        # 兼容旧版只保存 api_base 的设置：能匹配预设线路就反解成线路名。
        base = (saved.get("api_base") or "").strip().rstrip("/")
        if base:
            for name, url in API_DOMAIN_BASE_MAP.items():
                if url == base:
                    return name
            return CUSTOM_DOMAIN
        return DEFAULT_API_DOMAIN

    def _resolve_base(self, saved):
        if self.domain != CUSTOM_DOMAIN:
            base = API_DOMAIN_BASE_MAP[self.domain]
            return self.default_base if self.domain == DEFAULT_API_DOMAIN else base
        custom = (saved.get("api_base") or "").strip().rstrip("/")
        return custom if custom and _valid_api_base(custom) else self.default_base

    @staticmethod
    def _resolve_platform(saved):
        platform = saved.get("platform", DEFAULT_PLATFORM)
        allowed = {item["value"] for item in PLATFORM_OPTIONS}
        return platform if platform in allowed else DEFAULT_PLATFORM

    def settings(self):
        return {"api_domain": self.domain, "api_base": self.base, "platform": self.platform}

    def save_settings(self, values):
        if set(values) - {"api_domain", "api_base", "platform"}:
            raise ComicApiError("未知图源设置", 422, "invalid_request", self.id)

        saved = self.store.source_settings(self.id)
        merged = {"api_domain": saved.get("api_domain", ""), "api_base": saved.get("api_base", ""),
                  "platform": saved.get("platform", DEFAULT_PLATFORM)}

        if "platform" in values:
            platform = str(values.get("platform", DEFAULT_PLATFORM))
            if platform not in {item["value"] for item in PLATFORM_OPTIONS}:
                raise ComicApiError("无效的 platform 值", 422, "invalid_request", self.id)
            merged["platform"] = platform

        domain = str(values.get("api_domain", "") or "").strip()
        custom_base = str(values.get("api_base", "") or "").strip().rstrip("/")
        if domain in API_DOMAIN_BASE_MAP:
            merged["api_domain"], merged["api_base"] = domain, API_DOMAIN_BASE_MAP[domain]
        elif domain == CUSTOM_DOMAIN:
            # 自定义线路：未提交地址时沿用已保存的自定义地址
            custom_base = custom_base or merged["api_base"].rstrip("/") or self.default_base
            if not _valid_api_base(custom_base):
                raise ComicApiError("请输入不含凭据、查询参数、且以 /api/v3 开头的 HTTPS API 地址",
                                    422, "invalid_request", self.id)
            merged["api_domain"], merged["api_base"] = CUSTOM_DOMAIN, custom_base
        elif "api_base" in values:
            # 旧版只提交 api_base：空值恢复默认线路，合法地址视为自定义
            if not custom_base:
                merged["api_domain"], merged["api_base"] = DEFAULT_API_DOMAIN, self.default_base
            elif _valid_api_base(custom_base):
                merged["api_domain"], merged["api_base"] = CUSTOM_DOMAIN, custom_base
            else:
                raise ComicApiError("请输入不含凭据、查询参数、且以 /api/v3 开头的 HTTPS API 地址",
                                    422, "invalid_request", self.id)
        elif domain and domain != CUSTOM_DOMAIN:
            raise ComicApiError("未知的接口域名", 422, "invalid_request", self.id)

        self.store.save_source_settings(self.id, merged)
        # Replace the adapter for subsequent calls; already-running calls keep their old instance.
        replacement = type(self)(self.store)
        replacement.client = self.client
        replacement._chapter_lock = self._chapter_lock
        replacement._chapter_clock = self._chapter_clock
        return replacement

    def _api_headers(self):
        """参考插件：热辣漫画线路用独立 UA 特征，platform 走请求头。"""
        if _is_hot_manga_base(self.base):
            headers = {"Accept": "application/json", "version": "2025.02.12",
                       "Origin": "https://m.relamanhua.org", "webp": "1"}
        else:
            headers = {"Accept": "application/json", "version": "2025.05.09",
                       "Origin": "https://2025copy.com", "region": "0", "webp": "0"}
        if self.platform:
            headers["platform"] = self.platform
        return headers

    def _get(self, path, _app_fallback=False, **params):
        headers = APP_FALLBACK_HEADERS if _app_fallback else self._api_headers()
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
                if not _app_fallback and _is_anti_piracy_message(reason):
                    # 参考插件：命中反盗版提示时换 APP 请求头重试一次。
                    return self._get(path, _app_fallback=True, **params)
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
            # 热辣漫画线路优先 chapter，其余线路优先 chapter2（参考插件行为）。
            primary, secondary = ("chapter", "chapter2") if _is_hot_manga_base(self.base) else ("chapter2", "chapter")
            try:
                data = self._get(f"comic/{cid}/{primary}/{chapter}", platform=1)
            except ComicApiError as exc:
                if exc.status_code != 404:
                    raise
                data = self._get(f"comic/{cid}/{secondary}/{chapter}", platform=1)
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
                # 热辣漫画线路没有 update/newest，先按 comics 排序接口取（参考插件行为）。
                if _is_hot_manga_base(self.base):
                    raise ComicApiError("skip", 404, "not_found", self.id)
                data = self._get("update/newest", **params)
            except ComicApiError as exc:
                if exc.status_code != 404:
                    raise
                data = self._get("comics", ordering="-datetime_updated", **params)
        else:
            data = self._get("comics", theme=name, ordering=sort or "-datetime_updated", free_type=1, **params)
        return self._items(data)


create_plugin = CopyPlugin
