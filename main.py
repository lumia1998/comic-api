import asyncio
import hashlib
import io
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlencode, urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, Field

from src.errors import ComicApiError
from src.services.aggregator import AggregatorService
from src.services.downloads import DownloadManager, pdf_password_for
from src.storage import Store

load_dotenv()
ROOT = Path(__file__).resolve().parent
WEB_STATIC = ROOT / "src/web/static"
INDEX_HTML = ROOT / "src/web/templates/index.html"


def bundled_asset_version() -> str:
    """Content hash of the web bundle; changes whenever app.css/app.js change.

    The template links assets as ``?v=<token>``. Deriving the token from file
    contents (instead of a hand-bumped integer) is what keeps returning
    browsers from serving a stale bundle after a deploy.
    """
    digest = hashlib.sha256()
    for name in sorted(p.name for p in WEB_STATIC.glob("*") if p.is_file()):
        digest.update(name.encode("utf-8"))
        digest.update((WEB_STATIC / name).read_bytes())
    return digest.hexdigest()[:12]


def versioned_index_html() -> str:
    token = bundled_asset_version()
    return re.sub(r"\?v=[^\"'&]+", f"?v={token}", INDEX_HTML.read_text(encoding="utf-8"))


class VersionedStaticFiles(StaticFiles):
    """Immutable caching for hash-versioned URLs, revalidation for the rest."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            if scope.get("query_string"):
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            else:
                response.headers["Cache-Control"] = "no-cache"
        return response


class BookInput(BaseModel):
    category: str = Field(default="", max_length=100)


class TaskInput(BaseModel):
    source: str = Field(min_length=1, max_length=64)
    comic_id: str = Field(min_length=1, max_length=200)
    chapter_id: str = Field(min_length=1, max_length=200)
    title: str = Field(default="", max_length=500)
    chapter: str = Field(default="", max_length=500)


def create_app(store=None, sources=None):
    store = store or Store()
    service = AggregatorService(store, sources)
    downloads = DownloadManager(store, service)

    @asynccontextmanager
    async def lifespan(app):
        await downloads.start()
        yield
        await downloads.stop()

    app = FastAPI(title="Comic · 图源与书库", version="2.0.0", lifespan=lifespan)
    app.state.store, app.state.service, app.state.downloads = store, service, downloads
    app.mount("/static", VersionedStaticFiles(directory=WEB_STATIC), name="static")

    @app.exception_handler(ComicApiError)
    async def source_error(request, exc):
        return JSONResponse({"error": exc.payload()}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        return JSONResponse({"error": {"code": "invalid_request", "message": "请求参数无效"}}, status_code=422)

    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        logging.getLogger(__name__).exception("Request failed: %s", request.url.path)
        return JSONResponse({"error": {"code": "internal_error", "message": "服务内部错误"}}, status_code=500)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/")
    async def home():
        return HTMLResponse(versioned_index_html(), headers={"Cache-Control": "no-cache"})

    @app.get("/api/sources")
    async def sources_list():
        return {"sources": [plugin.manifest() for plugin in service.sources.values()]}

    @app.post("/api/sources/{source}/login")
    @app.post("/api/{source}/login", include_in_schema=False)
    async def login(source: str, values: dict[str, str]):
        plugin = service.source(source)
        if "login" not in plugin.capabilities:
            raise ComicApiError("该图源不提供登录", 400, "unsupported", source)
        if any(not values.get(field["name"], "").strip() for field in plugin.login_fields):
            raise ComicApiError("请填写全部登录字段", 422, "invalid_request", source)
        await service.call(source, "login", values)
        return {"success": True, "account": plugin.account_status()}

    @app.put("/api/sources/{source}/settings")
    async def save_source_settings(source: str, values: dict[str, str]):
        plugin = service.source(source)
        if not plugin.settings_fields:
            raise ComicApiError("该图源暂无可修改的服务器设置", 400, "unsupported", source)
        # Serialize updates on the event loop. Existing requests retain their adapter.
        service.sources[source] = plugin.save_settings(values)
        return {"success": True, "source": service.source(source).manifest()}

    @app.delete("/api/sources/{source}/account")
    async def logout(source: str):
        if "login" not in service.source(source).capabilities:
            raise ComicApiError("该图源不提供登录", 400, "unsupported", source)
        await service.call(source, "logout")
        return {"success": True}

    @app.get("/api/search")
    async def search(keyword: str = Query(min_length=1, max_length=200), source: str = "", page: int = Query(1, ge=1, le=1000)):
        if source:
            result = await service.call(source, "search", keyword, page)
            items = service.rank_results(keyword, [dict(item, source=source) for item in result])
            return {"items": items, "all_results": {source: items}, "errors": {}}
        return await service.aggregate_search(keyword)

    @app.get("/api/comic/{source}/{comic_id}")
    async def detail(source: str, comic_id: str):
        return await service.get_comic_detail(source, comic_id)

    @app.get("/api/chapter/{source}/{comic_id}/{chapter_id}")
    async def chapter(source: str, comic_id: str, chapter_id: str):
        urls = await service.get_chapter_images(source, comic_id, chapter_id)
        return {"images": ["/api/image/proxy?" + urlencode({"source": source, "url": url, "chapter_id": chapter_id}) for url in urls]}

    @app.get("/api/image/proxy")
    async def image(source: str, url: str, chapter_id: str = ""):
        if urlparse(url).scheme not in ("http", "https"):
            raise ComicApiError("图片地址无效", 400, "invalid_request")
        data = await service.image(source, url, chapter_id)
        try:
            with Image.open(io.BytesIO(data)) as img:
                media_type = Image.MIME.get(img.format, "image/jpeg")
        except Exception as exc:
            raise ComicApiError("图源未返回有效图片", 502, "invalid_image", source) from exc
        return Response(data, media_type=media_type)

    @app.get("/api/library")
    async def library(category: str | None = None):
        all_books = store.books()
        return {"items": all_books if category is None else [item for item in all_books if item["library_category"] == category],
                "categories": sorted({item["library_category"] for item in all_books if item["library_category"]})}

    @app.put("/api/library/{source}/{comic_id}")
    async def save_book(source: str, comic_id: str, data: BookInput):
        metadata = await service.get_comic_detail(source, comic_id)
        store.save_book(source, comic_id, metadata, data.category)
        return {"success": True}

    @app.patch("/api/library/{source}/{comic_id}")
    async def categorize(source: str, comic_id: str, data: BookInput):
        if not store.set_category(source, comic_id, data.category):
            raise ComicApiError("未收藏该漫画", 404, "not_found")
        return {"success": True}

    @app.post("/api/library/{source}/{comic_id}/refresh")
    async def refresh(source: str, comic_id: str):
        books = [book for book in store.books() if book["source"] == source and book["id"] == comic_id]
        if not books:
            raise ComicApiError("未收藏该漫画", 404, "not_found")
        metadata = await service.get_comic_detail(source, comic_id)
        old_ids = {str(item["id"]) for item in books[0].get("chapters", [])}
        new_ids = {str(item["id"]) for item in metadata.get("chapters", [])}
        store.save_book(source, comic_id, metadata, books[0]["library_category"])
        return {"success": True, "new_chapters": len(new_ids - old_ids)}

    @app.delete("/api/library/{source}/{comic_id}")
    async def remove_book(source: str, comic_id: str):
        store.remove_book(source, comic_id)
        return {"success": True}

    @app.get("/api/downloads")
    async def task_list():
        return {"tasks": store.tasks()}

    @app.post("/api/downloads", status_code=202)
    async def create_download(data: TaskInput):
        return downloads.create(**data.model_dump())

    @app.get("/api/downloads/{task_id}")
    async def download_status(task_id: str):
        return downloads.require(task_id)

    @app.post("/api/downloads/{task_id}/cancel")
    async def cancel_download(task_id: str):
        return downloads.cancel(task_id)

    @app.post("/api/downloads/{task_id}/retry")
    async def retry_download(task_id: str):
        return downloads.retry(task_id)

    @app.delete("/api/downloads/{task_id}")
    async def delete_download(task_id: str):
        downloads.delete(task_id)
        return {"success": True}

    @app.get("/api/downloads/{task_id}/file")
    async def download_file(task_id: str):
        task = downloads.require(task_id)
        path = downloads.file_path(task_id)
        if task["status"] != "completed" or not path.is_file():
            raise ComicApiError("文件尚未生成或已被清理", 404, "file_not_ready")
        return FileResponse(path, filename=f"{task['password']}.pdf", media_type="application/pdf")

    @app.get("/api/download/{source}/{comic_id}/{chapter_id}")
    async def legacy_download(source: str, comic_id: str, chapter_id: str, title: str = "", chapter: str = ""):
        task = downloads.create(source, comic_id, chapter_id, title, chapter)
        deadline = asyncio.get_running_loop().time() + 600
        while True:
            current = downloads.require(task["id"])
            if current["status"] == "completed":
                return await download_file(task["id"])
            if current["status"] in ("failed", "cancelled"):
                raise ComicApiError(current["error"] or "任务已取消", 502, "download_failed", source)
            if asyncio.get_running_loop().time() > deadline:
                try:
                    downloads.cancel(task["id"])
                except ComicApiError:
                    pass
                raise ComicApiError("下载超时", 504, "download_timeout", source)
            await asyncio.sleep(0.5)

    @app.get("/api/{source}/{action}")
    async def browse(source: str, action: str, page: int = Query(1, ge=1, le=1000), sort: str = "", mode: str = "day", name: str = ""):
        plugin = service.source(source)
        if action not in {"latest", "category", "leaderboard", "random"} or action not in plugin.capabilities:
            raise ComicApiError("图源不支持此功能", 400, "unsupported", source)
        items = await service.call(source, "browse", action, page=page, sort=sort, mode=mode, name=name)
        return {"success": True, "source": source, "data": [dict(item, source=source) for item in items]}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8699)
