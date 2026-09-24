"""Chapter fan-out downloads and adaptive PDF packaging."""
import asyncio
import io
import logging
import math
import os
import shutil
import tempfile
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image

from src.errors import ComicApiError, DownloadCancelled
from src.services.image_proxy import download_image

log = logging.getLogger("comic.pdf")


def _download_images_parallel(plugin, urls, out_dir, source="", chapter_id="",
                              concurrency=4, progress=None, cancelled=None):
    results = {}

    def download(url):
        if cancelled and cancelled():
            raise DownloadCancelled()
        data = download_image(plugin.client, url)
        if cancelled and cancelled():
            raise DownloadCancelled()
        return plugin.transform_image(data, chapter_id, url)

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(download, url): idx for idx, url in enumerate(urls)}
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                data = fut.result()
                if cancelled and cancelled():
                    raise DownloadCancelled()
                path_str = urllib.parse.urlparse(urls[idx]).path.lower()
                suffix = ".jpg"
                for ext in [".png", ".webp", ".gif", ".jpg", ".jpeg"]:
                    if path_str.endswith(ext):
                        suffix = ext
                        break
                p = os.path.join(out_dir, f"{idx + 1:04d}{suffix}")
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
                raise ComicApiError(f"图片 {idx + 1} 下载失败", 502, "image_download_failed", source) from e
    if len(results) != len(urls):
        raise Exception("部分图片下载失败")
    return [results[i] for i in sorted(results)]


def _make_pdf_bytes(image_paths, quality: int, scale: float) -> bytes:
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
        img_list[0].save(bio, "PDF", save_all=True, append_images=img_list[1:],
                         quality=quality, optimize=True)
        return bio.getvalue()
    finally:
        for img in img_list:
            try:
                img.close()
            except Exception:
                pass


def _create_compressed_pdf(image_paths, pdf_path: str, limit_bytes: float) -> None:
    qualities = [85, 60, 40, 20]
    scales = [1.0, 0.85, 0.7, 0.55]
    last_pdf_bytes = b""
    last_size = 0

    for scale in scales:
        for q in qualities:
            scale_text = f", 缩放 {scale:.2f}x" if scale < 1.0 else ""
            log.info("尝试以 JPEG 质量 %d%s 压缩 PDF ...", q, scale_text)
            pdf_bytes = _make_pdf_bytes(image_paths, q, scale)
            size = len(pdf_bytes)
            last_pdf_bytes = pdf_bytes
            last_size = size
            log.info("压缩结果体积: %.2fMB, 目标限额: %.2fMB",
                     size / (1024 * 1024), limit_bytes / (1024 * 1024))

            if size <= limit_bytes:
                with open(pdf_path, "wb") as f:
                    f.write(pdf_bytes)
                return

    log.warning("已尝试最低质量和最小缩放，文件体积 (%.1fMB) 仍超出限制，将直接发送。",
                last_size / (1024 * 1024))
    with open(pdf_path, "wb") as f:
        f.write(last_pdf_bytes)


def _encrypt_pdf(pdf_path: str, password: str) -> None:
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


async def build_chapter_pdf(service, source: str, comic_id: str, chapter_id: str,
                            concurrency: int = 4, password: str = "",
                            progress=None, cancelled=None) -> str:
    """下载章节并打包成自适应压缩的 PDF，返回本地临时 PDF 路径"""
    plugin = service.source(source)

    image_urls = await service.get_chapter_images(source, comic_id, chapter_id)
    if not image_urls:
        raise ComicApiError("该章节没有图片，或平台限制访问", status_code=404)
    if cancelled and cancelled():
        raise DownloadCancelled()
    if progress:
        progress("downloading", 0, len(image_urls))

    temp_dir = tempfile.mkdtemp(prefix="comic_api_dl_")
    try:
        loop = asyncio.get_running_loop()
        worker_count = max(1, min(int(concurrency), 16))
        all_paths = await loop.run_in_executor(
            None, _download_images_parallel, plugin, image_urls, temp_dir,
            source, chapter_id, worker_count, progress, cancelled)

        fd, pdf_path = tempfile.mkstemp(prefix="comic_", suffix=".pdf")
        os.close(fd)

        try:
            total = len(all_paths)
            if cancelled and cancelled():
                raise DownloadCancelled()
            if progress:
                progress("packaging", total, total)
            limit_bytes = 10 * math.ceil(total / 50) * 1024 * 1024

            await loop.run_in_executor(None, _create_compressed_pdf, all_paths, pdf_path, limit_bytes)
            await loop.run_in_executor(None, _encrypt_pdf, pdf_path, password)
            if cancelled and cancelled():
                raise DownloadCancelled()
            encrypted_size = os.path.getsize(pdf_path)
            if encrypted_size > limit_bytes:
                log.warning("加密后 PDF 体积 %.2fMB 超出目标限额 %.2fMB。",
                            encrypted_size / (1024 * 1024), limit_bytes / (1024 * 1024))
            return pdf_path
        except Exception:
            try:
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
            except Exception:
                pass
            raise
    finally:
        # Clean up image files and directory, but NOT the generated pdf_path itself
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
