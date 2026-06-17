import time
import json
import hashlib
import base64
from typing import List, Dict, Any, Tuple
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from src.config import Config
from src.clients.base import BaseClient

class JmClient(BaseClient):
    def __init__(self):
        super().__init__()
        self.api_bases = [Config.JM_FALLBACK_API_BASE]
        self.image_base = Config.JM_FALLBACK_IMAGE_BASE
        self.jwt_token = ""
        self.host_resolved = False

    def md5_hex(self, text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def decrypt_aes_ecb(self, payload_b64: str, key_hex: str) -> str:
        """AES-256-ECB decryption (key is 32-char hex string as utf-8 bytes)"""
        key = key_hex.encode("utf-8")
        raw_data = base64.b64decode(payload_b64)
        cipher = AES.new(key, AES.MODE_ECB)
        decrypted = cipher.decrypt(raw_data)
        return unpad(decrypted, 16).decode("utf-8")

    def decrypt_response(self, response_data: Any, ts: int) -> Any:
        if isinstance(response_data, bytes):
            if len(response_data) >= 2 and response_data[0] == 0x1f and response_data[1] == 0x8b:
                import zlib
                try:
                    response_data = zlib.decompress(response_data, 16 + zlib.MAX_WBITS).decode("utf-8")
                except Exception:
                    pass
        
        if isinstance(response_data, bytes):
            try:
                response_data = response_data.decode("utf-8")
            except Exception:
                return response_data

        if isinstance(response_data, str):
            try:
                response_data = json.loads(response_data)
            except Exception:
                return response_data

        if isinstance(response_data, dict):
            data_field = response_data.get("data")
            if data_field and isinstance(data_field, str):
                normalized = data_field.strip().replace("\n", "").replace("\r", "")
                ts_str = str(ts)
                for seed in Config.JM_SETTING_AES_SEEDS:
                    try:
                        key = self.md5_hex(f"{ts_str}{seed}")
                        decrypted = self.decrypt_aes_ecb(normalized, key)
                        return json.loads(decrypted)
                    except Exception:
                        continue
        return response_data

    def resolve_dynamic_hosts(self) -> bool:
        try:
            raw_pool_text = ""
            for url in Config.JM_HOST_CONFIG_URLS:
                try:
                    res = self.request("GET", url, timeout=8)
                    if res.status_code == 200:
                        raw_pool_text = res.text
                        break
                except Exception:
                    continue

            if not raw_pool_text:
                return False

            normalized = "".join(c for c in raw_pool_text if c.isalnum() or c in "+/=")
            key = self.md5_hex(Config.JM_HOSTCFG_AES_SEED)
            plain = self.decrypt_aes_ecb(normalized, key)
            parsed = json.loads(plain)
            
            server_list = parsed.get("Server", [])
            if not isinstance(server_list, list) or not server_list:
                return False

            ts_sec = str(int(time.time()))
            resolved_api_bases = []
            image_host = ""

            for domain in server_list:
                domain_url = domain if domain.startswith("http") else f"https://{domain}"
                domain_url = domain_url.rstrip("/")
                try:
                    setting_url = f"{domain_url}/setting?app_img_shunt=1&t={ts_sec}"
                    token = self.md5_hex(f"{ts_sec}{Config.JM_SECRET}")
                    
                    headers = {
                        "Tokenparam": f"{ts_sec},{Config.JM_VERSION}",
                        "Token": token,
                    }
                    res = self.request("GET", setting_url, headers=headers, timeout=8)
                    if res.status_code == 200:
                        decoded_settings = self.decrypt_response(res.content, int(ts_sec))
                        if isinstance(decoded_settings, dict):
                            image_host = decoded_settings.get("img_host", "")
                            resolved_api_bases.append(domain_url)
                            break
                except Exception:
                    continue

            if resolved_api_bases:
                self.api_bases = resolved_api_bases
                if image_host:
                    self.image_base = image_host if image_host.startswith("http") else f"https://{image_host}"
                    self.image_base = self.image_base.rstrip("/")
                self.host_resolved = True
                return True
        except Exception as e:
            print(f"[JmClient] Failed to resolve dynamic hosts: {e}")
        return False

    def get_api_headers(self, ts: int) -> dict:
        token = self.md5_hex(f"{ts}{Config.JM_VERSION}")
        headers = {
            "token": token,
            "tokenparam": f"{ts},{Config.JM_VERSION}",
            "accept-encoding": "gzip",
        }
        if self.jwt_token:
            headers["Authorization"] = f"Bearer {self.jwt_token}"
        return headers

    def jm_request(self, path: str, method: str = "GET", params: dict = None, data: dict = None) -> Any:
        if not self.host_resolved:
            self.resolve_dynamic_hosts()

        ts = int(time.time())
        headers = self.get_api_headers(ts)
        
        base_url = self.api_bases[0] if self.api_bases else Config.JM_FALLBACK_API_BASE
        url = f"{base_url}{path}"
        
        kwargs = {
            "headers": headers,
            "timeout": 12,
        }
        if params:
            kwargs["params"] = params
        if data:
            if method.upper() == "POST":
                kwargs["data"] = data
                headers["Content-Type"] = "application/x-www-form-urlencoded"

        try:
            res = self.request(method, url, **kwargs)
            if res.status_code < 200 or res.status_code >= 300:
                raise Exception(f"JM request failed with status: {res.status_code}")
        except Exception as e:
            self.host_resolved = False  # Reset on error to allow failover next time
            raise e

        decrypted = self.decrypt_response(res.content, ts)
        
        if isinstance(decrypted, dict) and "jwttoken" in decrypted:
            self.jwt_token = decrypted["jwttoken"]

        return decrypted

    def search(self, keyword: str, page: int = 1) -> List[Dict[str, Any]]:
        """搜索漫画 (修正：改回 GET 请求，params 传参，并加上直接 ID 检索跳转)"""
        keyword_clean = keyword.strip()
        keyword_lower = keyword_clean.lower()
        
        # 补全细节一：如果在第 1 页输入的是纯数字（大于等于100）或 jm 开头的 ID，直接拉取详情作为搜索结果
        if page == 1 and (keyword_clean.isdigit() and int(keyword_clean) >= 100 or keyword_lower.startswith("jm")):
            comic_id = keyword_clean[2:].strip() if keyword_lower.startswith("jm") else keyword_clean
            if comic_id:
                try:
                    detail = self.get_comic_detail(comic_id)
                    if detail and detail.get("title"):
                        return [{
                            "id": detail["id"],
                            "title": detail["title"],
                            "cover": detail["cover"],
                            "source": "jm",
                            "author": detail["author"],
                            "category": "",
                            "description": detail["description"]
                        }]
                except Exception:
                    pass  # 失败了则继续正常的网络检索

        try:
            res = self.jm_request("/search", method="GET", params={
                "search_query": keyword,
                "page": str(page)
            })
            
            # 如果是带 jm 前缀或全数字的 ID，可能触发直接加载详情结果返回
            data = res.get("data", res)
            if not isinstance(data, dict):
                return []
            
            # TS 里的 items 实际上是 map(toComicItem)
            # 在 /search 的返回值中，列表在 items 或是 content 字段
            content_list = data.get("items", []) or data.get("content", [])
            results = []
            for item in content_list:
                cid = str(item.get("id", ""))
                title = item.get("name", "") or item.get("title", "")
                if not cid or not title:
                    continue
                
                # 拼接封面 URL
                image_name = item.get("image", "")
                if image_name.startswith("http"):
                    cover_url = image_name
                else:
                    cover_url = f"{self.image_base}/media/albums/{cid}_3x4.jpg"
                
                results.append({
                    "id": cid,
                    "title": title,
                    "cover": cover_url,
                    "source": "jm",
                    "author": item.get("author", ""),
                    "category": item.get("category", {}).get("title", "") if isinstance(item.get("category"), dict) else "",
                    "description": item.get("description", "")
                })
            return results
        except Exception as e:
            print(f"[JmClient] search error: {e}")
            return []

    def get_comic_detail(self, comic_id: str) -> Dict[str, Any]:
        """获取漫画详情 (修正：改回 GET 请求，参数 id)"""
        try:
            res = self.jm_request("/album", method="GET", params={"id": comic_id})
            data = res.get("data", res)
            if not isinstance(data, dict):
                raise Exception("Invalid detail format")
                
            title = data.get("name", "")
            description = data.get("description", "")
            cover_url = f"{self.image_base}/media/albums/{comic_id}_3x4.jpg"
            
            series = data.get("series", [])
            chapters = []
            if not series:
                chapters.append({
                    "id": comic_id,
                    "name": "第1话 开始阅读",
                    "order": 1
                })
            else:
                for idx, ep in enumerate(series):
                    ch_id = str(ep.get("id", ""))
                    if not ch_id:
                        continue
                    ch_title = ep.get("name") or ep.get("title") or f"第{ep.get('sort', idx+1)}话"
                    chapters.append({
                        "id": ch_id,
                        "name": ch_title,
                        "order": idx + 1
                    })
                    
            return {
                "id": comic_id,
                "title": title,
                "cover": cover_url,
                "description": description,
                "author": "/".join(data.get("author", [])) if isinstance(data.get("author"), list) else data.get("author", ""),
                "chapters": chapters,
                "source": "jm"
            }
        except Exception as e:
            print(f"[JmClient] get_comic_detail error: {e}")
            return {}

    def get_chapter_images(self, comic_id: str, chapter_id: str) -> List[str]:
        """获取章节的所有图片链接 (修正：改回 GET 请求 /chapter, 参数 id)"""
        try:
            res = self.jm_request("/chapter", method="GET", params={"id": chapter_id, "skip": ""})
            data = res.get("data", res)
            if not isinstance(data, dict):
                return []
                
            images = data.get("images", [])
            image_urls = []
            
            for img in images:
                if isinstance(img, str):
                    img_name = img
                elif isinstance(img, dict):
                    img_name = img.get("path", "") or img.get("url", "")
                else:
                    continue
                
                if not img_name:
                    continue
                    
                if img_name.startswith("http"):
                    image_urls.append(img_name)
                else:
                    image_urls.append(f"{self.image_base}/media/photos/{chapter_id}/{img_name}")
            return image_urls
        except Exception as e:
            print(f"[JmClient] get_chapter_images error: {e}")
            return []

    def _parse_jm_comics(self, content_list: list) -> List[Dict[str, Any]]:
        """辅助解析禁漫返回的漫画列表"""
        results = []
        if not isinstance(content_list, list):
            return results
        for item in content_list:
            cid = str(item.get("id", ""))
            title = item.get("name", "") or item.get("title", "")
            if not cid or not title:
                continue
            image_name = item.get("image", "")
            if image_name.startswith("http"):
                cover_url = image_name
            else:
                cover_url = f"{self.image_base}/media/albums/{cid}_3x4.jpg"
            
            results.append({
                "id": cid,
                "title": title,
                "cover": cover_url,
                "source": "jm",
                "author": item.get("author", ""),
                "category": item.get("category", {}).get("title", "") if isinstance(item.get("category"), dict) else "",
                "description": item.get("description", "")
            })
        return results

    def get_recommend(self) -> List[Dict[str, Any]]:
        """获取推荐/热门推荐"""
        try:
            res = self.jm_request("/promote", method="GET", params={"page": "0"})
            # promote 接口返回通常是一个 section 数组，我们提取第一个 section 里的 content 作为本子
            if isinstance(res, list) and res:
                first_section = res[0]
                content = first_section.get("content", [])
                return self._parse_jm_comics(content)
            return []
        except Exception as e:
            print(f"[JmClient] get_recommend error: {e}")
            return []

    def get_latest(self, page: int = 1) -> List[Dict[str, Any]]:
        """获取最新更新本子"""
        try:
            res = self.jm_request("/latest", method="GET", params={"page": str(page - 1)})
            return self._parse_jm_comics(res)
        except Exception as e:
            print(f"[JmClient] get_latest error: {e}")
            return []

    def get_leaderboard(self, mode: str = "day", page: int = 1) -> List[Dict[str, Any]]:
        """获取排行榜 (day/week/month/total)"""
        # order 映射：mv_t(日), mv_w(周), mv_m(月), mv(总)
        order_map = {"day": "mv_t", "week": "mv_w", "month": "mv_m", "total": "mv"}
        order = order_map.get(mode, "mv_t")
        try:
            res = self.jm_request("/categories/filter", method="GET", params={
                "page": str(page - 1),
                "c": "",
                "o": order
            })
            content = res.get("content", [])
            return self._parse_jm_comics(content)
        except Exception as e:
            print(f"[JmClient] get_leaderboard error: {e}")
            return []

    def get_category_comics(self, category_name: str, page: int = 1, sort: str = "new") -> List[Dict[str, Any]]:
        """
        分类过滤 (同人/单本/短篇/韩漫 等)
        sort: new=最新, mv=最多观看, tf=最多收藏(喜欢), mp=最多指名
        """
        # 映射统一的 sort 关键词到 JM 的 o 参数
        order_map = {
            "new": "new",   # 最新上架
            "dd": "new",    # bika 别名兼容
            "mv": "mv",    # 最多观看
            "vd": "mv",    # bika 别名兼容
            "tf": "tf",    # 最多收藏/喜欢
            "ld": "tf",    # bika 别名兼容
            "mp": "mp",    # 最多指名
        }
        order = order_map.get(sort, "new")
        try:
            res = self.jm_request("/categories/filter", method="GET", params={
                "page": str(page - 1),
                "c": category_name,
                "o": order
            })
            content = res.get("content", [])
            return self._parse_jm_comics(content)
        except Exception as e:
            print(f"[JmClient] get_category_comics error: {e}")
            return []
