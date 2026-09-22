"""Trusted Python plugins: built-ins plus DATA_DIR/plugins/*.py, discovered at startup."""
import importlib
import importlib.util
import pkgutil
import re


class SourcePlugin:
    id = ""
    name = ""
    capabilities = ["search", "detail", "pages"]
    login_fields = []
    categories = []
    sorts = []
    leaderboard_modes = []
    settings_fields = []

    def __init__(self, store):
        self.store = store

    def account_status(self):
        return {"authenticated": False, "configured": False}

    def manifest(self):
        return {"id": self.id, "name": self.name, "capabilities": self.capabilities,
                "login_fields": self.login_fields, "categories": self.categories,
                "sorts": self.sorts, "leaderboard_modes": self.leaderboard_modes,
                "account": self.account_status(), "settings_fields": self.settings_fields,
                "settings": self.settings()}

    def settings(self):
        return {}

    def search(self, keyword, page=1):
        return self.client.search(keyword, page)

    def detail(self, comic_id):
        return self.client.get_comic_detail(comic_id)

    def pages(self, comic_id, chapter_id):
        return self.client.get_chapter_images(comic_id, chapter_id)

    def transform_image(self, data, chapter_id, url):
        return data


def load_sources(store):
    modules = [importlib.import_module(f"{__name__}.{item.name}")
               for item in pkgutil.iter_modules(__path__) if not item.name.startswith("_")]
    folder = store.root / "plugins"
    folder.mkdir(exist_ok=True)
    for path in sorted(folder.glob("*.py")):
        spec = importlib.util.spec_from_file_location(f"comic_plugin_{path.stem}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    result = {}
    for module in modules:
        factory = getattr(module, "create_plugin", None)
        if factory is None:
            continue
        plugin = factory(store)
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", plugin.id) or plugin.id in result:
            raise ValueError(f"Invalid or duplicate source ID: {plugin.id}")
        result[plugin.id] = plugin
    return result
