import asyncio
import hashlib
import os
import io
import ipaddress
import logging
import math
import shutil
import socket
import tempfile
import time
import urllib.parse
import unicodedata
from difflib import SequenceMatcher
from typing import List, Dict, Any
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.sources import load_sources
from src.storage import Store
from src.errors import ComicApiError, DownloadCancelled

log = logging.getLogger("comic.aggregator")


class AggregatorService:
    def __init__(self, store=None, sources=None):
        self.store = store or Store()
        self.sources = load_sources(self.store) if sources is None else sources
        self._slots = {key: asyncio.Semaphore(2) for key in self.sources}
        self._image_slots = asyncio.Semaphore(8)

    def source(self, source):
        if source not in self.sources:
            raise ComicApiError("未知图源", 404, "unknown_source", source)
        return self.sources[source]

    async def call(self, source, method, *args, **kwargs):
        plugin = self.source(source)
        operation = getattr(plugin, method, None)
        if not callable(operation):
            raise ComicApiError("图源不支持此功能", 400, "unsupported", source)
        slot = self._slots[source]
        try:
            await asyncio.wait_for(slot.acquire(), timeout=10)
        except asyncio.TimeoutError as exc:
            raise ComicApiError("图源繁忙，请稍后重试", 429, "busy", source) from exc
        # Cancellation must not release the permit while the underlying thread is running.
        task = asyncio.create_task(asyncio.to_thread(operation, *args, **kwargs))
        task.add_done_callback(lambda completed: (slot.release(), completed.exception() if not completed.cancelled() else None))
        try:
            return await asyncio.shield(task)
        except ComicApiError as exc:
            exc.source = source
            raise
        except Exception as exc:
            raise ComicApiError("图源响应异常，请稍后重试", 502, "upstream_error", source) from exc

    def get_similarity(self, a: str, b: str) -> float:
        """计算两个标题的相似度 (0.0 到 1.0)"""
        a_clean = a.lower().replace(" ", "").replace("-", "").replace("_", "")
        b_clean = b.lower().replace(" ", "").replace("-", "").replace("_", "")
        return SequenceMatcher(None, a_clean, b_clean).ratio()

    @staticmethod
    def normalize_title(value):
        return ''.join(c for c in unicodedata.normalize('NFKC', value).casefold() if c.isalnum())

    def rank_results(self, keyword, items):
        query = self.normalize_title(keyword)
        def score(item):
            title = self.normalize_title(item.get('title', ''))
            if not query or not title:
                return (0, 0)
            tier = 3 if query == title else 2 if query in title else 1
            return (tier, SequenceMatcher(None, query, title, autojunk=False).ratio())
        # Stable ties preserve upstream order; identical titles across sources stay selectable.
        return sorted(items, key=score, reverse=True)

    async def aggregate_search(self, keyword: str) -> Dict[str, Any]:
        """Search registered sources independently and retain partial failures."""
        keys = [key for key, plugin in self.sources.items() if "search" in plugin.capabilities]
        results = await asyncio.gather(*(self.call(key, "search", keyword) for key in keys), return_exceptions=True)
        all_results, errors, candidates = {}, {}, []
        for key, result in zip(keys, results):
            if isinstance(result, Exception):
                errors[key] = result.payload() if isinstance(result, ComicApiError) else {"message": "图源异常"}
                all_results[key] = []
            else:
                all_results[key] = [dict(item, source=key) for item in result]
                candidates.extend(all_results[key])
        candidates = self.rank_results(keyword, candidates)
        return {"keyword": keyword, "best_match": candidates[0] if candidates else None,
                "items": candidates, "all_results": all_results, "errors": errors}
        
    async def get_comic_detail(self, source: str, comic_id: str) -> Dict[str, Any]:
        """获取指定渠道下的漫画详情与章节"""
        result = await self.call(source, "detail", comic_id)
        if not result or not result.get("title"):
            raise ComicApiError("漫画不存在或图源未返回有效详情", 404, "not_found", source)
        return dict(result, source=source, id=comic_id)

    async def get_chapter_images(self, source: str, comic_id: str, chapter_id: str) -> List[str]:
        """获取指定渠道、漫画和章节下的图片"""
        return await self.call(source, "pages", comic_id, chapter_id)

    async def image(self, source, url, chapter_id=""):
        plugin = self.source(source)
        try:
            await asyncio.wait_for(self._image_slots.acquire(), timeout=10)
        except asyncio.TimeoutError as exc:
            raise ComicApiError("图片请求繁忙", 429, "busy", source) from exc
        key = hashlib.sha256(f"{source}:{url}".encode()).hexdigest()[:32]
        cache = self.store.root / "image_cache"
        path = cache / f"{key}.img"

        def process():
            if path.is_file():
                return path.read_bytes()
            self._ensure_public_url(url)
            data = plugin.transform_image(self._download_image(plugin.client, url), chapter_id, url)
            try:
                cache.mkdir(exist_ok=True)
                path.write_bytes(data)
                self._trim_image_cache(cache)
            except OSError:
                pass
            return data

        task = asyncio.create_task(asyncio.to_thread(process))
        task.add_done_callback(lambda done: (self._image_slots.release(), done.exception() if not done.cancelled() else None))
        return await asyncio.shield(task)

    @staticmethod
    def _trim_image_cache(cache, keep=2000):
        files = sorted(cache.iterdir(), key=lambda item: item.stat().st_mtime)
        for stale in files[:-keep]:
            try:
                stale.unlink()
            except OSError:
                pass

    @staticmethod
    def _ensure_public_url(url):
        """The proxy endpoint takes user-supplied URLs; refuse private/reserved addresses."""
        hostname = urllib.parse.urlparse(url).hostname or ""
        try:
            addresses = {entry[4][0] for entry in socket.getaddrinfo(hostname, None)}
        except OSError as exc:
            raise ComicApiError("图片地址无法解析", 502, "image_dns_failed") from exc
        for address in addresses:
            try:
                if not ipaddress.ip_address(address).is_global:
                    raise ComicApiError("图片地址不被允许", 400, "invalid_request")
            except ValueError:
                raise ComicApiError("图片地址不被允许", 400, "invalid_request")

    def _download_image(self, client: Any, url: str, retries: int = 3) -> bytes:
        """使用 Client 自身的 BaseClient.request 来下载图片二进制。

        JM 图片 CDN 节点不稳定，单张图常随机返回 403/连接重置，
        因此加入重试+退避，避免单次失败导致整张图裂掉。
        """
        # JM 图片服务对 Referer 较敏感，使用站点根域而非图片自身 URL
        parsed = urllib.parse.urlparse(url)
        referer = f"{parsed.scheme}://{parsed.netloc}/"
        headers = {
            "Referer": referer,
            "User-Agent": client.ua,
        }

        last_err = None
        for attempt in range(max(1, retries)):
            try:
                res = client.request("GET", url, headers=headers, timeout=30)
                if res.status_code == 200 and res.content:
                    return res.content
                status = res.status_code
                last_err = ComicApiError(f"图片下载失败 (HTTP {status})", status if status in (401,403,404,429) else 502, "image_download_failed")
                if status in (401,403,404):
                    break
            except Exception as e:
                last_err = e

            # 退避后重试（0.5s, 1s, ...）
            if attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))

        raise last_err or Exception(f"Failed to download image from {url}")

    def _download_images_parallel(self, client: Any, urls: List[str], out_dir: str, source: str = "", chapter_id: str = "", concurrency: int = 4, progress=None, cancelled=None) -> List[str]:
        results = {}
        def download(url):
            if cancelled and cancelled():
                raise DownloadCancelled()
            data = self._download_image(client, url)
            if cancelled and cancelled():
                raise DownloadCancelled()
            return self.source(source).transform_image(data, chapter_id, url)
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {
                pool.submit(download, url): idx
                for idx, url in enumerate(urls)
            }
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    data = fut.result()
                    
                    if cancelled and cancelled():
                        raise DownloadCancelled()
                    
                    # Determine extension from url or fallback to .jpg
                    path_str = urllib.parse.urlparse(urls[idx]).path.lower()
                    suffix = ".jpg"
                    for ext in [".png", ".webp", ".gif", ".jpg", ".jpeg"]:
                          if path_str.endswith(ext):
                              suffix = ext
                              break
                    p = os.path.join(out_dir, f"{idx+1:04d}{suffix}")
                    with open(p, "wb") as f:
                        f.write(data)
                    results[idx] = p
                    if progress:
                        progress("downloading", len(results), len(urls))
                except DownloadCancelled:
                    for pending in futures:
                        pending.cancel()
                    raise
                except Exception as e:
                    for pending in futures:
                        pending.cancel()
                    raise ComicApiError(f"图片 {idx+1} 下载失败", 502, "image_download_failed", source) from e
        if len(results) != len(urls):
            raise Exception("部分图片下载失败")
        return [results[i] for i in sorted(results)]

    def _make_pdf_bytes(self, image_paths: List[str], quality: int, scale: float) -> bytes:
        img_list = []
        resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.LANCZOS)
        try:
            for p in sorted(image_paths, key=lambda x: os.path.basename(x)):
                with Image.open(p) as img:
                    if img.mode != "RGB":
                        work = img.convert("RGB")
                    else:
                        work = img.copy()
                    if scale < 1.0:
                        width, height = work.size
                        new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
                        work = work.resize(new_size, resampling)
                    img_list.append(work)

            if not img_list:
                raise ComicApiError("该章节没有可打包的图片", status_code=404)

            bio = io.BytesIO()
            img_list[0].save(bio, "PDF", save_all=True, append_images=img_list[1:], quality=quality, optimize=True)
            return bio.getvalue()
        finally:
            for img in img_list:
                try:
                    img.close()
                except Exception:
                    pass

    def _create_compressed_pdf(self, image_paths: List[str], pdf_path: str, limit_bytes: float) -> None:
        qualities = [85, 60, 40, 20]
        scales = [1.0, 0.85, 0.7, 0.55]
        last_pdf_bytes = b""
        last_size = 0

        for scale in scales:
            for q in qualities:
                scale_text = f", 缩放 {scale:.2f}x" if scale < 1.0 else ""
                log.info("尝试以 JPEG 质量 %d%s 压缩 PDF ...", q, scale_text)
                pdf_bytes = self._make_pdf_bytes(image_paths, q, scale)
                size = len(pdf_bytes)
                last_pdf_bytes = pdf_bytes
                last_size = size
                log.info("压缩结果体积: %.2fMB, 目标限额: %.2fMB", size / (1024 * 1024), limit_bytes / (1024 * 1024))

                if size <= limit_bytes:
                    with open(pdf_path, "wb") as f:
                        f.write(pdf_bytes)
                    return

        log.warning(
            "已尝试最低质量和最小缩放，文件体积 (%.1fMB) 仍超出限制，将直接发送。",
            last_size / (1024 * 1024),
        )
        with open(pdf_path, "wb") as f:
            f.write(last_pdf_bytes)

    def _encrypt_pdf(self, pdf_path: str, password: str) -> None:
        if not password:
            return
        try:
            from pypdf import PdfReader, PdfWriter
        except ImportError as e:
            raise Exception("pypdf is required to encrypt PDF output") from e

        reader = PdfReader(pdf_path)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)

        try:
            writer.encrypt(user_password=password, owner_password=password, algorithm="AES-256")
        except TypeError:
            writer.encrypt(password)

        encrypted_path = f"{pdf_path}.encrypted"
        try:
            with open(encrypted_path, "wb") as f:
                writer.write(f)
            os.replace(encrypted_path, pdf_path)
        finally:
            if os.path.exists(encrypted_path):
                try:
                    os.remove(encrypted_path)
                except Exception:
                    pass

    async def download_chapter_pdf(self, source: str, comic_id: str, chapter_id: str, concurrency: int = 4, password: str = "", progress=None, cancelled=None) -> str:
        """下载章节并打包成自适应压缩的 PDF，返回本地临时 PDF 路径"""
        client = self.source(source).client

        # Fetch chapter images first
        image_urls = await self.get_chapter_images(source, comic_id, chapter_id)
        if not image_urls:
            raise ComicApiError("该章节没有图片，或平台限制访问", status_code=404)
        if cancelled and cancelled():
            raise DownloadCancelled()
        if progress:
            progress("downloading", 0, len(image_urls))

        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix="comic_api_dl_")
        try:
            # Download images in parallel
            loop = asyncio.get_running_loop()
            worker_count = max(1, min(int(concurrency), 16))
            all_paths = await loop.run_in_executor(
                None, self._download_images_parallel, client, image_urls, temp_dir, source, chapter_id, worker_count, progress, cancelled
            )

            # Package and dynamically compress to PDF
            # We will generate a final PDF in the system temp directory and return its path
            fd, pdf_path = tempfile.mkstemp(prefix="comic_", suffix=".pdf")
            os.close(fd)

            try:
                total = len(all_paths)
                if cancelled and cancelled():
                    raise DownloadCancelled()
                if progress:
                    progress("packaging", total, total)
                limit_bytes = 10 * math.ceil(total / 50) * 1024 * 1024

                await loop.run_in_executor(
                    None, self._create_compressed_pdf, all_paths, pdf_path, limit_bytes
                )
                await loop.run_in_executor(None, self._encrypt_pdf, pdf_path, password)
                if cancelled and cancelled():
                    raise DownloadCancelled()
                encrypted_size = os.path.getsize(pdf_path)
                if encrypted_size > limit_bytes:
                    log.warning(
                        "加密后 PDF 体积 %.2fMB 超出目标限额 %.2fMB。",
                        encrypted_size / (1024 * 1024), limit_bytes / (1024 * 1024),
                    )
                return pdf_path
            except Exception as e:
                try:
                    if os.path.exists(pdf_path):
                        os.remove(pdf_path)
                except Exception:
                    pass
                raise e
        finally:
            # Clean up image files and directory, but NOT the generated pdf_path itself
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

