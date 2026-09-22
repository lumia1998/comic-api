import asyncio
import hashlib
import os
import threading
import uuid

from src.errors import ComicApiError, DownloadCancelled


def pdf_password_for(source, comic_id, chapter_id):
    seed = f"{source.strip().lower()}:{comic_id}:{chapter_id}".encode()
    return f"{int(hashlib.sha256(seed).hexdigest()[:12], 16) % 1000000:06d}"


class DownloadManager:
    """One worker bounds CPU/PDF memory. Image concurrency is capped by the service."""
    def __init__(self, store, service):
        self.store, self.service = store, service
        self.directory = store.root / "downloads"
        self.directory.mkdir(exist_ok=True)
        self.queue = asyncio.Queue(maxsize=100)
        self.signals = {}
        self.worker = None

    async def start(self):
        with self.store.connect() as db:
            db.execute("UPDATE downloads SET status='failed', stage='interrupted', error='服务重启中断，请重试' WHERE status IN ('running','cancelling','queued')")
        self.worker = asyncio.create_task(self.run())

    async def stop(self):
        for signal in self.signals.values():
            signal.set()
        # Let threads finish cleanup before the event loop is closed.
        if self.worker:
            await self.queue.put(None)
            await self.worker

    def require(self, task_id):
        task = self.store.task(task_id)
        if not task:
            raise ComicApiError("任务不存在", 404, "not_found")
        return task

    def create(self, source, comic_id, chapter_id, title="", chapter=""):
        self.service.source(source)
        if self.queue.full():
            raise ComicApiError("下载队列已满", 429, "busy")
        task_id = uuid.uuid4().hex
        password = pdf_password_for(source, comic_id, chapter_id)
        with self.store.connect() as db:
            db.execute("INSERT INTO downloads(id,source,comic_id,chapter_id,title,chapter,password) VALUES (?,?,?,?,?,?,?)",
                       (task_id, source, comic_id, chapter_id, title, chapter, password))
        self.signals[task_id] = threading.Event()
        self.queue.put_nowait(task_id)
        return self.require(task_id)

    def cancel(self, task_id):
        task = self.require(task_id)
        if task["status"] not in ("queued", "running", "cancelling"):
            raise ComicApiError("任务已结束", 409, "invalid_state")
        self.signals[task_id].set()
        self.store.update_task(task_id, status="cancelling" if task["status"] != "queued" else "cancelled")
        return self.require(task_id)

    def retry(self, task_id):
        task = self.require(task_id)
        # A cancelled queued item may still be in the in-memory queue.
        if task["status"] not in ("failed", "cancelled") or task_id in self.signals:
            raise ComicApiError("请等待任务停止后重试", 409, "invalid_state")
        if self.queue.full():
            raise ComicApiError("下载队列已满", 429, "busy")
        self.service.source(task["source"])
        self.store.update_task(task_id, status="queued", stage="queued", completed=0, total=0, error="")
        self.signals[task_id] = threading.Event()
        self.queue.put_nowait(task_id)
        return self.require(task_id)

    def delete(self, task_id):
        task = self.require(task_id)
        if task_id in self.signals or task["status"] in ("running", "cancelling", "queued"):
            raise ComicApiError("请先取消任务并等待停止", 409, "invalid_state")
        self.file_path(task_id).unlink(missing_ok=True)
        with self.store.connect() as db:
            db.execute("DELETE FROM downloads WHERE id=?", (task_id,))

    def file_path(self, task_id):
        self.require(task_id)
        # IDs always originate in our database, never use request paths as filenames.
        if len(task_id) != 32 or any(c not in "0123456789abcdef" for c in task_id):
            raise ComicApiError("非法任务编号", 400, "invalid_request")
        return self.directory / f"{task_id}.pdf"

    async def run(self):
        while True:
            task_id = await self.queue.get()
            if task_id is None:
                self.queue.task_done()
                return
            signal = self.signals[task_id]
            result = None
            try:
                if signal.is_set():
                    raise DownloadCancelled()
                task = self.require(task_id)
                self.store.update_task(task_id, status="running", stage="fetching")
                result = await self.service.download_chapter_pdf(
                    task["source"], task["comic_id"], task["chapter_id"], password=task["password"],
                    cancelled=signal.is_set,
                    progress=lambda stage, completed, total: self.store.update_task(task_id, stage=stage, completed=completed, total=total))
                if signal.is_set():
                    raise DownloadCancelled()
                # Temporary output may reside on a different filesystem than the data volume.
                import shutil
                await asyncio.to_thread(shutil.move, result, self.file_path(task_id))
                if signal.is_set():
                    self.file_path(task_id).unlink(missing_ok=True)
                    raise DownloadCancelled()
                self.store.update_task(task_id, status="completed", stage="completed")
            except DownloadCancelled:
                self.store.update_task(task_id, status="cancelled", stage="cancelled")
            except Exception as exc:
                self.store.update_task(task_id, status="failed", stage="failed",
                                       error=str(exc) if isinstance(exc, ComicApiError) else "下载或打包失败，请重试")
            finally:
                if result and os.path.exists(result):
                    os.remove(result)
                self.signals.pop(task_id, None)
                self.queue.task_done()
