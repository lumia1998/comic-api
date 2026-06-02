import asyncio
import hashlib
import os
import io
import math
import shutil
import tempfile
import urllib.parse
from difflib import SequenceMatcher
from typing import List, Dict, Any
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.clients import JmClient, BikaClient

class AggregatorService:
    def __init__(self):
        self.jm = JmClient()
        self.bika = BikaClient()

    def get_similarity(self, a: str, b: str) -> float:
        """计算两个标题的相似度 (0.0 到 1.0)"""
        a_clean = a.lower().replace(" ", "").replace("-", "").replace("_", "")
        b_clean = b.lower().replace(" ", "").replace("-", "").replace("_", "")
        return SequenceMatcher(None, a_clean, b_clean).ratio()

    async def _async_search(self, client: Any, source_name: str, keyword: str) -> List[Dict[str, Any]]:
        """异步封装 Client 的阻塞搜索调用"""
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, client.search, keyword, 1)
        except Exception as e:
            print(f"[Aggregator] {source_name} search error: {e}")
            return []

    async def aggregate_search(self, keyword: str) -> Dict[str, Any]:
        """
        聚合搜索核心：
        1. 并发查询 jm, bika
        2. 计算与关键字的相似度
        3. 优先级为 jm > bika
        4. 返回最佳匹配以及全渠道结果
        """
        tasks = [
            self._async_search(self.jm, "jm", keyword),
            self._async_search(self.bika, "bika", keyword)
        ]
        
        jm_res, bika_res = await asyncio.gather(*tasks)

        all_results = {
            "jm": jm_res,
            "bika": bika_res
        }

        candidates = []
        # 优先级：jm (2) > bika (1)
        
        for item in jm_res:
            sim = self.get_similarity(keyword, item["title"])
            candidates.append((sim, 2, item))
            
        for item in bika_res:
            sim = self.get_similarity(keyword, item["title"])
            candidates.append((sim, 1, item))

        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)

        best_match = None
        if candidates:
            best_match = candidates[0][2]

        return {
            "keyword": keyword,
            "best_match": best_match,
            "all_results": all_results
        }
        
    async def get_comic_detail(self, source: str, comic_id: str) -> Dict[str, Any]:
        """获取指定渠道下的漫画详情与章节"""
        loop = asyncio.get_running_loop()
        client = None
        if source == "jm":
            client = self.jm
        elif source == "bika":
            client = self.bika
            
        if not client:
            return {}
            
        try:
            return await loop.run_in_executor(None, client.get_comic_detail, comic_id)
        except Exception as e:
            print(f"[Aggregator] get_comic_detail error source={source} id={comic_id}: {e}")
            return {}

    async def get_chapter_images(self, source: str, comic_id: str, chapter_id: str) -> List[str]:
        """获取指定渠道、漫画和章节下的图片"""
        loop = asyncio.get_running_loop()
        client = None
        if source == "jm":
            client = self.jm
        elif source == "bika":
            client = self.bika
            
        if not client:
            return []
            
        try:
            return await loop.run_in_executor(None, client.get_chapter_images, comic_id, chapter_id)
        except Exception as e:
            print(f"[Aggregator] get_chapter_images error source={source} ch_id={chapter_id}: {e}")
            return []

    def _download_image(self, client: Any, url: str) -> bytes:
        """使用 Client 自身的 BaseClient.request 来下载图片二进制"""
        headers = {
            "Referer": url,
            "User-Agent": client.ua
        }
        res = client.request("GET", url, headers=headers, timeout=30)
        if res.status_code != 200:
            raise Exception(f"Failed to download image from {url}: status={res.status_code}")
        return res.content

    def _jm_image_filename(self, url: str) -> str:
        path = urllib.parse.urlparse(url).path
        filename = path.rsplit("/", 1)[-1]
        if "." in filename:
            filename = filename.rsplit(".", 1)[0]
        return filename or ""

    def _jm_scramble_num(self, chapter_id: str, filename: str) -> int:
        try:
            ch_id = int(str(chapter_id).strip())
        except Exception:
            return 0
        if ch_id < 220980:
            return 0
        if ch_id < 268850:
            return 10

        modulus = 10 if ch_id < 421926 else 8
        digest = hashlib.md5(f"{ch_id}{filename}".encode("utf-8")).hexdigest()
        value = ord(digest[-1]) % modulus
        return value * 2 + 2

    def _descramble_jm_image(self, data: bytes, chapter_id: str, image_url: str) -> bytes:
        filename = self._jm_image_filename(image_url)
        scramble_num = self._jm_scramble_num(chapter_id, filename)
        if scramble_num <= 1:
            return data

        with Image.open(io.BytesIO(data)) as img:
            width, height = img.size
            slice_height = height // scramble_num
            remainder = height % scramble_num
            if slice_height <= 0:
                return data

            fixed = Image.new(img.mode, (width, height))
            for index in range(scramble_num):
                src_y = height - slice_height * (index + 1) - remainder
                dst_y = slice_height * index + (0 if index == 0 else remainder)
                current_height = slice_height + (remainder if index == 0 else 0)
                box = (0, src_y, width, src_y + current_height)
                fixed.paste(img.crop(box), (0, dst_y))

            output = io.BytesIO()
            fixed.save(output, format=img.format or "JPEG")
            return output.getvalue()

    def _download_images_parallel(self, client: Any, urls: List[str], out_dir: str, source: str = "", chapter_id: str = "", concurrency: int = 4) -> List[str]:
        results = {}
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {
                pool.submit(self._download_image, client, url): idx
                for idx, url in enumerate(urls)
            }
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    data = fut.result()
                    
                    # Apply JmComic descrambling if source is jm
                    if source == "jm" and chapter_id:
                        try:
                            data = self._descramble_jm_image(data, chapter_id, urls[idx])
                        except Exception as e:
                            print(f"[comic-api] JmComic descramble error: {e}")
                    
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
                except Exception as e:
                    raise Exception(f"图片 {idx+1} 下载失败: {e}")
        if len(results) != len(urls):
            raise Exception("部分图片下载失败")
        return [results[i] for i in sorted(results)]

    def _create_compressed_pdf(self, image_paths: List[str], pdf_path: str, limit_bytes: float) -> None:
        qualities = [85, 60, 40, 20]
        img_list = []
        try:
            for p in sorted(image_paths, key=lambda x: os.path.basename(x)):
                img = Image.open(p)
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img_list.append(img)
                
            for q in qualities:
                print(f"[comic-api] 尝试以 JPEG 质量 {q} 压缩 PDF ...", flush=True)
                bio = io.BytesIO()
                img_list[0].save(bio, "PDF", save_all=True, append_images=img_list[1:], quality=q, optimize=True)
                pdf_bytes = bio.getvalue()
                size = len(pdf_bytes)
                print(f"[comic-api] 压缩结果体积: {size / (1024 * 1024):.2f}MB, 目标限额: {limit_bytes / (1024 * 1024):.2f}MB", flush=True)
                
                if size <= limit_bytes or q == qualities[-1]:
                    if size > limit_bytes:
                        print(f"[comic-api] 警告：已尝试最低质量，文件体积 ({size / (1024 * 1024):.1f}MB) 仍超出限制，将直接发送。", flush=True)
                    with open(pdf_path, "wb") as f:
                        f.write(pdf_bytes)
                    break
        finally:
            for img in img_list:
                try:
                    img.close()
                except Exception:
                    pass

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

    async def download_chapter_pdf(self, source: str, comic_id: str, chapter_id: str, concurrency: int = 4, password: str = "") -> str:
        """下载章节并打包成自适应压缩的 PDF，返回本地临时 PDF 路径"""
        client = None
        if source == "jm":
            client = self.jm
        elif source == "bika":
            client = self.bika
        if not client:
            raise Exception(f"Invalid source: {source}")

        # Fetch chapter images first
        image_urls = await self.get_chapter_images(source, comic_id, chapter_id)
        if not image_urls:
            raise Exception("该章节没有图片，或平台限制访问")

        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix="comic_api_dl_")
        try:
            # Download images in parallel
            loop = asyncio.get_running_loop()
            worker_count = max(1, min(int(concurrency), 16))
            all_paths = await loop.run_in_executor(
                None, self._download_images_parallel, client, image_urls, temp_dir, source, chapter_id, worker_count
            )

            # Package and dynamically compress to PDF
            # We will generate a final PDF in the system temp directory and return its path
            fd, pdf_path = tempfile.mkstemp(prefix="comic_", suffix=".pdf")
            os.close(fd)

            try:
                total = len(all_paths)
                limit_bytes = 10 * math.ceil(total / 50) * 1024 * 1024

                await loop.run_in_executor(
                    None, self._create_compressed_pdf, all_paths, pdf_path, limit_bytes
                )
                await loop.run_in_executor(None, self._encrypt_pdf, pdf_path, password)
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

