import time
import os
from pathlib import Path
import uuid
import hmac
import hashlib
import json
import math
import threading
from typing import List, Dict, Any
from urllib.parse import urlparse, urlencode
from src.config import Config
from src.clients.base import BaseClient

class BikaClient(BaseClient):
    def __init__(self):
        super().__init__()
        self.api_base = Config.BIKA_DEFAULT_API_BASE
        self._auth_lock = threading.RLock()
        self.authorization = ""
        data_dir = os.environ.get("DATA_DIR", "")
        if data_dir:
            self.token_file = os.path.join(data_dir, ".bika_token")
        else:
            self.token_file = str(Path(__file__).resolve().parents[2] / ".bika_token")
        self.credentials_file = os.path.join(os.path.dirname(self.token_file), ".bika_credentials.json")

        stored_account, stored_password = self._read_persisted_credentials()
        if stored_account and stored_password:
            self._account = stored_account
            self._password = stored_password
        else:
            self._account = os.environ.get("BIKA_ACCOUNT", "").strip()
            self._password = os.environ.get("BIKA_PASSWORD", "")

        self.authorization = self._read_persisted_token()

    def _read_persisted_credentials(self):
        try:
            if os.path.exists(self.credentials_file):
                with open(self.credentials_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                account = str(data.get("account", "")).strip()
                password = str(data.get("password", ""))
                if account and password:
                    return account, password
        except Exception as e:
            print(f"[BikaClient] Load credentials error: {e}")
        return "", ""

    def _read_persisted_token(self) -> str:
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, "r", encoding="utf-8") as f:
                    return f.read().strip()
        except Exception as e:
            print(f"[BikaClient] Load token error: {e}")
        return ""

    def _atomic_write(self, file_path: str, content: str) -> None:
        token_dir = os.path.dirname(file_path) or "."
        os.makedirs(token_dir, exist_ok=True)
        temp_file = f"{file_path}.{os.getpid()}.{threading.get_ident()}.tmp"
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, file_path)
        finally:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass

    def _persist_token(self, token: str) -> None:
        self._atomic_write(self.token_file, token)

    def _persist_credentials(self, account: str, password: str) -> None:
        credentials = json.dumps(
            {"account": account, "password": password},
            ensure_ascii=False,
        )
        self._atomic_write(self.credentials_file, credentials)

    def _clear_authorization_locked(self, expected_token: str = "") -> None:
        if expected_token and self.authorization not in ("", expected_token):
            return

        self.authorization = ""
        if not os.path.exists(self.token_file):
            return

        try:
            persisted_token = self._read_persisted_token()
            if not expected_token or persisted_token == expected_token:
                os.remove(self.token_file)
        except Exception as e:
            print(f"[BikaClient] Remove token error: {e}")

    def _credentials_available(self) -> bool:
        return bool(self._account and self._password)

    def ensure_authenticated(self) -> None:
        if self.authorization:
            return

        with self._auth_lock:
            if self.authorization:
                return

            persisted_token = self._read_persisted_token()
            if persisted_token:
                self.authorization = persisted_token
                return

            if not self._credentials_available():
                raise Exception("哔咔未登录，请在 .env 配置账号密码或在后台绑定账号。")

            self._login_locked(self._account, self._password)

    def clean_path(self, path: str) -> str:
        """提取纯路径，包括后面的 Query String"""
        if path.startswith("http"):
            try:
                parsed = urlparse(path)
                query = f"?{parsed.query}" if parsed.query else ""
                path = f"{parsed.path}{query}"
            except Exception:
                pass
        return path.lstrip("/")

    def create_signature(self, path: str, timestamp: int, nonce: str, method: str) -> str:
        """
        hmac-sha256 签名计算：
        raw = (path + timestamp + nonce + method + api_key).lower()
        """
        raw = f"{path}{timestamp}{nonce}{method}{Config.BIKA_API_KEY}".lower()
        secret = Config.BIKA_SECRET_KEY.encode("utf-8")
        signature = hmac.new(secret, raw.encode("utf-8"), hashlib.sha256).hexdigest()
        return signature

    def _send_bika_request(
        self,
        path: str,
        method: str = "GET",
        params: dict = None,
        json_body: dict = None,
        authorization: str = "",
    ):
        url = f"{self.api_base}{path}"
        
        # 核心修复：如果存在 params，必须将其拼接到签名 path 的尾部！
        sign_path = path
        if params:
            query_str = urlencode(params)
            if query_str:
                sign_path = f"{path}?{query_str}"

        cleaned_path = self.clean_path(sign_path)
        
        timestamp = int(time.time())
        nonce = uuid.uuid4().hex
        
        signature = self.create_signature(cleaned_path, timestamp, nonce, method)
        
        headers = {
            "api-key": Config.BIKA_API_KEY,
            "accept": "application/vnd.picacomic.com.v1+json",
            "app-channel": "3",
            "time": str(timestamp),
            "nonce": nonce,
            "signature": signature,
            "app-version": "2.2.1.3.3.4",
            "app-uuid": "defaultUuid",
            "app-platform": "android",
            "app-build-version": "45",
            "user-agent": "okhttp/3.8.1",
            "content-type": "application/json; charset=UTF-8",
            "image-quality": "original"
        }
        
        if authorization:
            headers["authorization"] = authorization
            
        kwargs = {
            "headers": headers,
            "timeout": 15
        }
        if params:
            kwargs["params"] = params
            
        if json_body is not None:
            kwargs["data"] = json.dumps(json_body).encode("utf-8")
            
        return self.request(method, url, **kwargs)

    @staticmethod
    def _response_error(res) -> str:
        try:
            return str(res.json().get("message", ""))
        except Exception:
            return ""

    @staticmethod
    def _is_auth_failure(res, err_msg: str) -> bool:
        return res.status_code == 401 or err_msg.lower() == "unauthorized"

    def _login_locked(self, account: str, password: str) -> str:
        res = self._send_bika_request(
            "auth/sign-in",
            method="POST",
            json_body={"email": account, "password": password},
            authorization="",
        )
        if res.status_code < 200 or res.status_code >= 300:
            err_msg = self._response_error(res)
            raise Exception(f"Bika request failed status={res.status_code} error={err_msg}")

        token = res.json().get("data", {}).get("token", "")
        if not token:
            raise Exception("哔咔登录成功但响应中没有 Token。")

        self._persist_credentials(account, password)
        self._persist_token(token)
        self._account = account
        self._password = password
        self.authorization = token
        return token

    def _refresh_authorization(self, failed_token: str) -> None:
        with self._auth_lock:
            if self.authorization and self.authorization != failed_token:
                return

            persisted_token = self._read_persisted_token()
            if persisted_token and persisted_token != failed_token:
                self.authorization = persisted_token
                return

            if not self._credentials_available():
                self._clear_authorization_locked(failed_token)
                raise Exception("哔咔登录已失效，且未配置 BIKA_ACCOUNT/BIKA_PASSWORD。")

            try:
                self._login_locked(self._account, self._password)
            except Exception:
                self._clear_authorization_locked(failed_token)
                raise

    def bika_request(
        self,
        path: str,
        method: str = "GET",
        params: dict = None,
        json_body: dict = None,
        _auth_retry: bool = False,
    ) -> Any:
        used_token = self.authorization
        res = self._send_bika_request(path, method, params, json_body, used_token)
        if res.status_code < 200 or res.status_code >= 300:
            err_msg = self._response_error(res)
            if self._is_auth_failure(res, err_msg):
                if used_token and not _auth_retry:
                    self._refresh_authorization(used_token)
                    return self.bika_request(path, method, params, json_body, _auth_retry=True)

                if used_token:
                    with self._auth_lock:
                        self._clear_authorization_locked(used_token)

            raise Exception(f"Bika request failed status={res.status_code} error={err_msg}")

        return res.json()

    def login(self, account: str, password: str) -> str:
        """登录哔咔"""
        account = account.strip()
        if not account or not password:
            raise Exception("哔咔账号和密码不能为空。")
        with self._auth_lock:
            return self._login_locked(account, password)

    def search(self, keyword: str, page: int = 1) -> List[Dict[str, Any]]:
        """搜索漫画"""
        self.ensure_authenticated()
            
        try:
            res = self.bika_request("comics/advanced-search", method="POST", params={
                "page": str(page)
            }, json_body={
                "keyword": keyword,
                "sort": "dd",
                "categories": []
            })
            
            data = res.get("data", {})
            comics = data.get("comics", {})
            docs = comics.get("docs", []) if isinstance(comics, dict) else (comics if isinstance(comics, list) else [])
            
            results = []
            for item in docs:
                cid = str(item.get("_id", "") or item.get("id", ""))
                title = item.get("title", "")
                if not cid or not title:
                    continue
                
                cover = item.get("thumb", {})
                cover_url = ""
                if isinstance(cover, dict):
                    cover_url = f"{cover.get('fileServer', '')}/static/{cover.get('path', '')}"
                
                results.append({
                    "id": cid,
                    "title": title,
                    "cover": cover_url,
                    "source": "bika",
                    "author": item.get("author", ""),
                    "category": " · ".join(item.get("categories", [])) if isinstance(item.get("categories"), list) else "",
                    "description": item.get("description", "")
                })
            return results
        except Exception as e:
            print(f"[BikaClient] search error: {e}")
            return []

    def get_comic_detail(self, comic_id: str) -> Dict[str, Any]:
        """获取详情并加载全部章节分页"""
        self.ensure_authenticated()
            
        try:
            res = self.bika_request(f"comics/{comic_id}", method="GET")
            data = res.get("data", {}).get("comic", {})
            title = data.get("title", "")
            description = data.get("description", "")
            
            cover = data.get("thumb", {})
            cover_url = ""
            if isinstance(cover, dict):
                cover_url = f"{cover.get('fileServer', '')}/static/{cover.get('path', '')}"
                
            eps_count = int(data.get("epsCount", 0))
            total_pages = max(1, math.ceil(eps_count / 40))
            
            eps_docs = []
            for page in range(1, total_pages + 1):
                try:
                    eps_res = self.bika_request(f"comics/{comic_id}/eps", method="GET", params={"page": str(page)})
                    eps_docs.extend(eps_res.get("data", {}).get("eps", {}).get("docs", []))
                except Exception:
                    break
            
            chapters = []
            for idx, doc in enumerate(eps_docs):
                ch_id = str(doc.get("order", ""))
                if not ch_id:
                    continue
                ch_name = doc.get("title") or doc.get("name") or f"第{doc.get('order', idx+1)}话"
                chapters.append({
                    "id": ch_id,
                    "name": ch_name,
                    "order": int(ch_id)
                })
                
            chapters.sort(key=lambda x: x["order"])
            
            return {
                "id": comic_id,
                "title": title,
                "cover": cover_url,
                "description": description,
                "author": data.get("author", ""),
                "chapters": chapters,
                "source": "bika"
            }
        except Exception as e:
            print(f"[BikaClient] get_comic_detail error: {e}")
            return {}

    def get_chapter_images(self, comic_id: str, chapter_id: str) -> List[str]:
        """获取章节页面图片"""
        self.ensure_authenticated()
            
        try:
            image_urls = []
            page = 1
            total_pages = 1
            
            while page <= total_pages:
                res = self.bika_request(f"comics/{comic_id}/order/{chapter_id}/pages", method="GET", params={"page": str(page)})
                data = res.get("data", {})
                pages_meta = data.get("pages", {})
                
                total_pages = int(pages_meta.get("pages", 1))
                docs = pages_meta.get("docs", [])
                
                for doc in docs:
                    media = doc.get("media", {})
                    if isinstance(media, dict):
                        img_url = f"{media.get('fileServer', '')}/static/{media.get('path', '')}"
                        image_urls.append(img_url)
                
                page += 1
                
            return image_urls
        except Exception as e:
            print(f"[BikaClient] get_chapter_images error: {e}")
            return []

    def _parse_comics_list(self, raw_res: dict) -> List[Dict[str, Any]]:
        """内部辅助解析哔咔返回的漫画数组"""
        data = raw_res.get("data", {})
        comics = data.get("comics", {})
        docs = comics.get("docs", []) if isinstance(comics, dict) else (comics if isinstance(comics, list) else [])
        
        results = []
        for item in docs:
            cid = str(item.get("_id", "") or item.get("id", ""))
            title = item.get("title", "")
            if not cid or not title:
                continue
            cover = item.get("thumb", {})
            cover_url = ""
            if isinstance(cover, dict):
                cover_url = f"{cover.get('fileServer', '')}/static/{cover.get('path', '')}"
            results.append({
                "id": cid,
                "title": title,
                "cover": cover_url,
                "source": "bika",
                "author": item.get("author", ""),
                "category": " · ".join(item.get("categories", [])) if isinstance(item.get("categories"), list) else "",
                "description": item.get("description", "")
            })
        return results

    def get_random(self) -> List[Dict[str, Any]]:
        """获取随机本子"""
        try:
            self.ensure_authenticated()
            res = self.bika_request("comics/random", method="GET")
            return self._parse_comics_list(res)
        except Exception as e:
            print(f"[BikaClient] get_random error: {e}")
            return []

    def get_leaderboard(self, mode: str = "day") -> List[Dict[str, Any]]:
        """获取排行榜 (day/week/month)"""
        days_map = {"day": "H24", "week": "D7", "month": "D30"}
        days = days_map.get(mode, "H24")
        try:
            self.ensure_authenticated()
            res = self.bika_request("comics/leaderboard", method="GET", params={"tt": days, "ct": "VC"})
            return self._parse_comics_list(res)
        except Exception as e:
            print(f"[BikaClient] get_leaderboard error: {e}")
            return []

    def get_category_comics(self, category_name: str, page: int = 1, sort: str = "dd") -> List[Dict[str, Any]]:
        """
        筛选分类下的本子
        sort: dd=最新, da=最旧, ld=最多喜欢, vd=最多观看
        """
        valid_sorts = {"dd", "da", "ld", "vd"}
        s = sort if sort in valid_sorts else "dd"
        try:
            self.ensure_authenticated()
            res = self.bika_request("comics", method="GET", params={"page": str(page), "c": category_name, "s": s})
            return self._parse_comics_list(res)
        except Exception as e:
            print(f"[BikaClient] get_category_comics error: {e}")
            return []

    def get_latest(self, page: int = 1, sort: str = "dd") -> List[Dict[str, Any]]:
        """
        获取本子列表（支持排序）
        sort: dd=最新, da=最旧, ld=最多喜欢, vd=最多观看
        """
        valid_sorts = {"dd", "da", "ld", "vd"}
        s = sort if sort in valid_sorts else "dd"
        try:
            self.ensure_authenticated()
            res = self.bika_request("comics", method="GET", params={"page": str(page), "s": s})
            return self._parse_comics_list(res)
        except Exception as e:
            print(f"[BikaClient] get_latest error: {e}")
            return []
