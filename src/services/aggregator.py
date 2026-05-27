import asyncio
from difflib import SequenceMatcher
from typing import List, Dict, Any
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
