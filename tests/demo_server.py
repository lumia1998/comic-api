"""Offline browser QA server; never loaded by the production application."""
import os
import tempfile

os.environ['DATA_DIR'] = tempfile.mkdtemp(prefix='comic-ui-qa-')
from main import create_app
from src.storage import Store
from tests.fakes import DemoPlugin
from src.sources.copy import CopyPlugin

store = Store(os.environ['DATA_DIR'])
guest = DemoPlugin(store)
guest.id, guest.name, guest.capabilities = 'guest', '游客测试图源', ['search', 'detail', 'pages']
app = create_app(store, {'demo': DemoPlugin(store), 'guest': guest, 'copy': CopyPlugin(store)})
