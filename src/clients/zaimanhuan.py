import time
from typing import List, Dict, Any
from src.config import Config
from src.clients.base import BaseClient

class ZaiManHuanClient(BaseClient):
    def __init__(self):
        super().__init__()
        self.api_base = Config.ZMH_API_BASE
        self.auth_token = ""

    def get_default_params(self) -> dict:
        return {
            "platform": "android",
            "timestamp": str(int(time.time())),
            "_v": Config.ZMH_APP_VERSION,
            "_c": Config.ZMH_APP_CHANNEL
        }

    def get_default_headers(self) -> dict:
        headers = {
            "Accept": "application/json"
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def zmh_request(self, path: str, method: str = "GET", params: dict = None, data: dict = None) -> Any:
        url = f"{self.api_base}{path}"
        headers = self.get_default_headers()
        
        # 合并默认参数
        all_params = self.get_default_params()
        if params:
            all_params.update(params)
            
        kwargs = {
            "headers": headers,
            "params": all_params,
            "timeout": 10
        }
        if data:
            kwargs["data"] = data
            
        res = self.request(method, url, **kwargs)
        if res.status_code < 200 or res.status_code >= 300:
            raise Exception(f"ZaiManHuan request failed with status: {res.status_code}")
            
        return res.json()

    def search(self, keyword: str, page: int = 1) -> List[Dict[str, Any]]:
        """搜索漫画"""
        try:
            res = self.zmh_request("/search/index", method="GET", params={
                "keyword": keyword,
                "page": str(page),
                "sort": "0",
                "size": "20"
            })
            
            if res.get("errno") != 0:
                print(f"[ZaiManHuan] search failed: {res.get('errmsg')}")
                return []
                
            data = res.get("data", {})
            comic_list = data.get("list", [])
            results = []
            for item in comic_list:
                cid = str(item.get("comic_id", "") or item.get("id", ""))
                title = item.get("title", "")
                if not cid or not title:
                    continue
                results.append({
                    "id": cid,
                    "title": title,
                    "cover": item.get("cover", ""),
                    "source": "zaimanhuan",
                    "author": item.get("authors", ""),
                    "category": item.get("types", ""),
                    "description": item.get("last_update_chapter_name", "")
                })
            return results
        except Exception as e:
            print(f"[ZaiManHuan] search error: {e}")
            return []

    def get_comic_detail(self, comic_id: str) -> Dict[str, Any]:
        """获取漫画详情"""
        try:
            res = self.zmh_request(f"/comic/detail/{comic_id}", method="GET")
            if res.get("errno") != 0:
                raise Exception(res.get("errmsg", "Unknown error"))
                
            data = res.get("data", {})
            comic_info = data.get("comic_info", data)
            title = comic_info.get("title", "")
            description = comic_info.get("description", "")
            cover = comic_info.get("cover", "")
            
            # 解析作者名
            authors_list = comic_info.get("authors", [])
            author_names = [a.get("tag_name", "") for a in authors_list]
            author = " · ".join(filter(None, author_names))
            
            # 解析章节列表
            chapters_groups = comic_info.get("chapters", [])
            chapters = []
            order_idx = 1
            for grp in chapters_groups:
                grp_data = grp.get("data", [])
                for ep in grp_data:
                    ch_id = str(ep.get("chapter_id", ""))
                    if not ch_id:
                        continue
                    chapters.append({
                        "id": ch_id,
                        "name": ep.get("chapter_title", f"第{order_idx}话"),
                        "order": order_idx
                    })
                    order_idx += 1
            
            # 如果没有章节组，说明可能是单话或未分配
            if not chapters:
                chapters.append({
                    "id": comic_id,
                    "name": "第1话 开始阅读",
                    "order": 1
                })

            return {
                "id": comic_id,
                "title": title,
                "cover": cover,
                "description": description,
                "author": author,
                "chapters": chapters,
                "source": "zaimanhuan"
            }
        except Exception as e:
            print(f"[ZaiManHuan] get_comic_detail error: {e}")
            return {}

    def get_chapter_images(self, comic_id: str, chapter_id: str) -> List[str]:
        """获取章节页面图片列表"""
        try:
            res = self.zmh_request(f"/comic/chapter/{comic_id}/{chapter_id}", method="GET")
            if res.get("errno") != 0:
                raise Exception(res.get("errmsg", "Unknown error"))
                
            data_info = res.get("data", {}).get("data", {})
            
            # 部分章节可能包含 page_url_hd （高清），部分包含 page_url
            images = data_info.get("page_url_hd", []) or data_info.get("page_url", [])
            return [str(url).strip() for url in images if url]
        except Exception as e:
            print(f"[ZaiManHuan] get_chapter_images error: {e}")
            return []
