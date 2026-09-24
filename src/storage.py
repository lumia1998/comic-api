"""Single-instance SQLite storage. Reader progress deliberately does not live here."""
import base64
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from Crypto.Cipher import AES


class Store:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get("DATA_DIR") or Path(__file__).resolve().parents[1] / "data")
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "comic.sqlite"
        key_path = self.root / "credentials.key"
        if self.path.exists() and not key_path.exists():
            raise RuntimeError("Missing credentials.key; restore it with the database backup")
        try:
            fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "wb") as stream:
                stream.write(os.urandom(32))
        self.key = key_path.read_bytes()
        if len(self.key) != 32:
            raise RuntimeError("Invalid credentials.key; restore it with the database backup")
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS accounts (
                    source TEXT PRIMARY KEY, secret TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS source_settings (
                    source TEXT PRIMARY KEY, settings TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS library (
                    source TEXT NOT NULL, comic_id TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '', metadata TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(source, comic_id)
                );
                CREATE TABLE IF NOT EXISTS downloads (
                    id TEXT PRIMARY KEY, source TEXT NOT NULL, comic_id TEXT NOT NULL,
                    chapter_id TEXT NOT NULL, title TEXT NOT NULL, chapter TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued', stage TEXT NOT NULL DEFAULT 'queued',
                    completed INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL DEFAULT 0,
                    error TEXT NOT NULL DEFAULT '', password TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                PRAGMA user_version=1;
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def account(self, source):
        with self.connect() as db:
            row = db.execute("SELECT secret FROM accounts WHERE source=?", (source,)).fetchone()
        if row is None:
            return None
        payload = base64.b64decode(row["secret"])
        cipher = AES.new(self.key, AES.MODE_GCM, nonce=payload[:16])
        cipher.update(source.encode())
        return json.loads(cipher.decrypt_and_verify(payload[32:], payload[16:32]))

    def source_settings(self, source):
        with self.connect() as db:
            row = db.execute("SELECT settings FROM source_settings WHERE source=?", (source,)).fetchone()
        return json.loads(row[0]) if row else {}

    def save_source_settings(self, source, values):
        with self.connect() as db:
            db.execute("INSERT INTO source_settings VALUES (?,?) ON CONFLICT(source) DO UPDATE SET settings=excluded.settings",
                       (source, json.dumps(values)))

    def save_account(self, source, values):
        cipher = AES.new(self.key, AES.MODE_GCM)
        cipher.update(source.encode())
        data, tag = cipher.encrypt_and_digest(json.dumps(values).encode())
        secret = base64.b64encode(cipher.nonce + tag + data).decode()
        with self.connect() as db:
            db.execute("INSERT INTO accounts VALUES (?,?) ON CONFLICT(source) DO UPDATE SET secret=excluded.secret", (source, secret))

    def books(self):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM library ORDER BY updated_at DESC").fetchall()
        return [dict(json.loads(r["metadata"]), source=r["source"], id=r["comic_id"], library_category=r["category"], updated_at=r["updated_at"])
                for r in rows]

    def save_book(self, source, comic_id, metadata, category=""):
        with self.connect() as db:
            db.execute("""INSERT INTO library(source,comic_id,metadata,category) VALUES (?,?,?,?)
                ON CONFLICT(source,comic_id) DO UPDATE SET metadata=excluded.metadata,
                category=excluded.category, updated_at=CURRENT_TIMESTAMP""",
                       (source, comic_id, json.dumps(metadata, ensure_ascii=False), category))

    def set_category(self, source, comic_id, category):
        with self.connect() as db:
            return db.execute("UPDATE library SET category=? WHERE source=? AND comic_id=?",
                              (category, source, comic_id)).rowcount

    def remove_book(self, source, comic_id):
        with self.connect() as db:
            db.execute("DELETE FROM library WHERE source=? AND comic_id=?", (source, comic_id))

    def tasks(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM downloads ORDER BY created_at DESC, rowid DESC")]

    def task(self, task_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM downloads WHERE id=?", (task_id,)).fetchone()
        return dict(row) if row else None

    def update_task(self, task_id, **values):
        allowed = {"status", "stage", "completed", "total", "error"}
        if not values or not values.keys() <= allowed:
            raise ValueError("Invalid task update")
        with self.connect() as db:
            db.execute("UPDATE downloads SET " + ",".join(f"{k}=?" for k in values) +
                       ",updated_at=CURRENT_TIMESTAMP WHERE id=?", (*values.values(), task_id))
