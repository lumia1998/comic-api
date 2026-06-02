import hashlib
import os
from fastapi import FastAPI, Request, Query, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from src.services.aggregator import AggregatorService, ComicApiError

app = FastAPI(
    title="Aggregated Comic API",
    description="Multisource aggregate manga lookup engine (JM, Bika)",
    version="1.0.0"
)

os.makedirs("src/web/static", exist_ok=True)
os.makedirs("src/web/templates", exist_ok=True)

app.mount("/static", StaticFiles(directory="src/web/static"), name="static")
templates = Jinja2Templates(directory="src/web/templates")

aggregator = AggregatorService()

def pdf_password_for(source: str, comic_id: str, chapter_id: str) -> str:
    seed = f"{source.strip().lower()}:{comic_id}:{chapter_id}".encode("utf-8")
    value = int(hashlib.sha256(seed).hexdigest()[:12], 16) % 1000000
    return f"{value:06d}"

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def home_index(request: Request):
    """前端首页"""
    bika_authed = bool(aggregator.bika.authorization)
    return templates.TemplateResponse("index.html", {"request": request, "bika_authed": bika_authed})

@app.get("/api/search")
async def api_search(keyword: str = Query(..., min_length=1)):
    """聚合搜索接口"""
    results = await aggregator.aggregate_search(keyword)
    return results

@app.get("/api/comic/{source}/{comic_id}")
async def api_comic_detail(source: str, comic_id: str):
    """漫画详情 (章节列表)"""
    detail = await aggregator.get_comic_detail(source, comic_id)
    return detail

@app.get("/api/chapter/{source}/{comic_id}/{chapter_id}")
async def api_chapter_images(source: str, comic_id: str, chapter_id: str):
    """章节图片"""
    images = await aggregator.get_chapter_images(source, comic_id, chapter_id)
    return {"images": images}

@app.post("/api/bika/login")
async def api_bika_login(data: dict):
    """哔咔登录接口"""
    account = data.get("account", "").strip()
    password = data.get("password", "")
    if not account or not password:
        return {"success": False, "error": "账号和密码不能为空"}
        
    try:
        token = aggregator.bika.login(account, password)
        return {"success": True, "token": token}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/download/{source}/{comic_id}/{chapter_id}")
async def api_download_chapter(
    source: str,
    comic_id: str,
    chapter_id: str,
    background_tasks: BackgroundTasks,
    title: str = Query(""),
    chapter: str = Query(""),
    password: str = Query(""),
    concurrency: int = Query(4, ge=1, le=16)
):
    """下载章节并打包成自适应压缩的 PDF"""
    try:
        pdf_password = password or pdf_password_for(source, comic_id, chapter_id)
        pdf_path = await aggregator.download_chapter_pdf(
            source,
            comic_id,
            chapter_id,
            concurrency=concurrency,
            password=pdf_password,
        )
        
        filename = f"{pdf_password}.pdf"

        # Register background task to clean up the temporary PDF file
        def remove_temp_file(path: str):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                print(f"[comic-api] Error removing temp file {path}: {e}")

        background_tasks.add_task(remove_temp_file, pdf_path)

        return FileResponse(
            path=pdf_path,
            filename=filename,
            media_type="application/pdf"
        )
    except ComicApiError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

# ==================== 新增高阶玩法的 API 路由 ====================

@app.get("/api/{source}/random")
async def api_random(source: str):
    """
    随机本子/推荐接口
    http://127.0.0.1:8699/api/bika/random
    http://127.0.0.1:8699/api/jm/random (使用推荐替代)
    """
    if source == "bika":
        return {"success": True, "source": "bika", "data": aggregator.bika.get_random()}
    elif source == "jm":
        return {"success": True, "source": "jm", "data": aggregator.jm.get_recommend()}
    return {"success": False, "error": "Invalid source"}

@app.get("/api/{source}/leaderboard")
async def api_leaderboard(source: str, mode: str = "day", page: int = 1):
    """
    排行榜接口
    - source: jm / bika
    - mode: day (日榜), week (周榜), month (月榜), total (总榜，仅限 jm)
    http://127.0.0.1:8699/api/jm/leaderboard?mode=week
    """
    if source == "bika":
        data = aggregator.bika.get_leaderboard(mode)
        # 客户端侧分页 (每页 20 条结果)
        page_size = 20
        start = (page - 1) * page_size
        end = start + page_size
        sliced_data = data[start:end] if start < len(data) else []
        return {"success": True, "source": "bika", "data": sliced_data}
    elif source == "jm":
        return {"success": True, "source": "jm", "data": aggregator.jm.get_leaderboard(mode, page)}
    return {"success": False, "error": "Invalid source"}

@app.get("/api/{source}/latest")
async def api_latest(source: str, page: int = 1, sort: str = "dd"):
    """
    最近更新接口 (哔咔支持排序)
    sort: dd=最新上架, da=最旧上架, ld=最多喜欢, vd=最多观看
    http://127.0.0.1:8699/api/jm/latest?page=1
    http://127.0.0.1:8699/api/bika/latest?page=1&sort=ld
    """
    if source == "bika":
        return {"success": True, "source": "bika", "data": aggregator.bika.get_latest(page, sort)}
    elif source == "jm":
        return {"success": True, "source": "jm", "data": aggregator.jm.get_latest(page)}
    return {"success": False, "error": "Invalid source"}

@app.get("/api/{source}/category")
async def api_category(source: str, name: str, page: int = 1, sort: str = "dd"):
    """
    分类筛选接口 (两平台均支持排序)
    - name: 哔咔分类(例如 '嗶咔漢化', '同人') / 禁漫分类(例如 'doujin', 'single')
    - sort 通用值: dd=最新, ld=最多喜欢/收藏, vd=最多观看, da=最旧(仅bika)
    - sort 禁漫专属值: new=最新, mv=最多观看, tf=最多收藏, mp=最多指名
    http://127.0.0.1:8699/api/bika/category?name=同人&sort=ld
    http://127.0.0.1:8699/api/jm/category?name=doujin&sort=mv
    """
    if source == "bika":
        return {"success": True, "source": "bika", "data": aggregator.bika.get_category_comics(name, page, sort)}
    elif source == "jm":
        return {"success": True, "source": "jm", "data": aggregator.jm.get_category_comics(name, page, sort)}
    return {"success": False, "error": "Invalid source"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8699, reload=True)
