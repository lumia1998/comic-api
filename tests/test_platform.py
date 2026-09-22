import asyncio
import json
import threading
import time
import types

import pytest
from fastapi.testclient import TestClient

from src.storage import Store
from src.sources import load_sources
from src.sources.copy import CopyPlugin
from src.clients.bika import BikaClient
from src.errors import ComicApiError
from src.services.aggregator import AggregatorService
from src.services.downloads import DownloadManager
from tests.fakes import DemoPlugin


def test_account_encryption_and_isolation(tmp_path):
    store = Store(tmp_path)
    store.save_account("one", {"password": "super-secret"})
    store.save_account("two", {"token": "other-secret"})
    assert Store(tmp_path).account("one")["password"] == "super-secret"
    assert store.account("two") == {"token": "other-secret"}
    with store.connect() as db:
        assert "super-secret" not in db.execute("SELECT secret FROM accounts WHERE source='one'").fetchone()[0]


def test_legacy_migration_and_logout_no_resurrection(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("BIKA_ACCOUNT", "environment")
    monkeypatch.setenv("BIKA_PASSWORD", "environment-password")
    (tmp_path / ".bika_credentials.json").write_text(json.dumps({"account": "legacy", "password": "secret"}))
    (tmp_path / ".bika_token").write_text("legacy-token")
    store = Store(tmp_path)
    client = BikaClient(store)
    assert client._account == "legacy" and client.authorization == "legacy-token"
    client._persist_token("refreshed")
    assert BikaClient(store).authorization == "refreshed"
    store.save_account("bika", {})
    other = BikaClient(store)
    assert other.authorization == other._account == other._password == ""


def test_expired_bika_session_refreshes(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    store = Store(tmp_path)
    store.save_account("bika", {"account": "a", "password": "p", "token": "old"})
    client = BikaClient(store)
    responses = iter([types.SimpleNamespace(status_code=401, json=lambda:{"message":"unauthorized"}),
                      types.SimpleNamespace(status_code=200, json=lambda:{"data":{"token":"new"}}),
                      types.SimpleNamespace(status_code=200, json=lambda:{"ok":True})])
    monkeypatch.setattr(client,"_send_bika_request",lambda *a,**k:next(responses))
    assert client.bika_request("test") == {"ok":True}
    assert store.account("bika")["token"] == "new"


def test_external_plugin_discovery(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    store = Store(tmp_path)
    folder = tmp_path / "plugins"
    folder.mkdir()
    (folder / "extra.py").write_text('from src.sources import SourcePlugin\nclass Extra(SourcePlugin):\n id="extra"\n name="Extra"\ncreate_plugin=Extra\n')
    assert "extra" in load_sources(store)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from main import create_app
    store = Store(tmp_path)
    plugin = DemoPlugin(store)
    with TestClient(create_app(store, {plugin.id:plugin})) as client:
        yield client


def test_dynamic_login_no_secret_in_responses(client):
    assert client.get('/api/sources').json()['sources'][0]['id']=='demo'
    response=client.post('/api/sources/demo/login',json={'account':'alice','password':'private'})
    assert response.status_code==200
    assert 'private' not in response.text and 'test-token' not in response.text
    assert 'private' not in client.get('/api/sources').text
    assert client.delete('/api/sources/demo/account').status_code==200


def test_library_crud_and_no_server_read_progress(client):
    path='/api/library/demo/same-id'
    assert client.put(path,json={'category':'收藏'}).status_code==200
    assert client.put(path,json={'category':'收藏'}).status_code==200
    assert len(client.get('/api/library').json()['items'])==1
    assert client.patch(path,json={'category':'追更'}).status_code==200
    assert client.get('/api/library?category=追更').json()['items'][0]['library_category']=='追更'
    assert client.post(path+'/refresh').json()['new_chapters']==0
    with client.app.state.store.connect() as db:
        tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables=={'accounts','library','downloads','source_settings'}
    assert client.delete(path).status_code==200
    assert client.get('/api/library').json()['items']==[]


def test_empty_results_are_distinct_from_source_errors(client):
    empty=client.get('/api/search?keyword=empty').json()
    failed=client.get('/api/search?keyword=fail').json()
    assert empty['errors']=={} and empty['all_results']['demo']==[]
    assert failed['errors']['demo']['code']=='login_required'
    assert client.get('/api/search?keyword=fail&source=demo').status_code==401
    assert client.get('/api/comic/missing/1').status_code==404
    assert client.get('/api/demo/category').status_code==400


def test_download_e2e(client):
    task=client.post('/api/downloads',json={'source':'demo','comic_id':'1','chapter_id':'1'}).json()
    for _ in range(100):
        current=client.app.state.store.task(task['id'])
        if current['status'] in ('completed','failed'):break
        time.sleep(.05)
    assert current['status']=='completed',current
    assert current['completed']==current['total']==3
    assert client.get(f"/api/downloads/{task['id']}").json()['status']=='completed'
    response=client.get(f"/api/downloads/{task['id']}/file")
    assert response.status_code==200 and response.content.startswith(b'%PDF')
    assert client.post(f"/api/downloads/{task['id']}/retry").status_code==409
    assert client.delete(f"/api/downloads/{task['id']}").status_code==200
    assert client.get(f"/api/downloads/{task['id']}/file").status_code==404


def test_task_cancel_retry_and_restart(tmp_path):
    async def scenario():
        store=Store(tmp_path)
        fake=DemoPlugin(store)
        service=AggregatorService(store,{'demo':fake})
        manager=DownloadManager(store,service)
        await manager.start()
        first=manager.create('demo','1','1')
        manager.cancel(first['id'])
        await manager.queue.join()
        assert store.task(first['id'])['status']=='cancelled'
        manager.retry(first['id'])
        await manager.queue.join()
        assert store.task(first['id'])['status']=='completed'
        store.update_task(first['id'],status='running')
        await manager.stop()
        restarted=DownloadManager(Store(tmp_path),service)
        await restarted.start()
        assert store.task(first['id'])['stage']=='interrupted'
        await restarted.stop()
    asyncio.run(scenario())


def test_active_cancellation(tmp_path):
    async def scenario():
        store=Store(tmp_path);fake=DemoPlugin(store);fake.delay=.1
        service=AggregatorService(store,{'demo':fake});manager=DownloadManager(store,service)
        await manager.start();task=manager.create('demo','1','1')
        await asyncio.sleep(.04);manager.cancel(task['id']);await manager.queue.join()
        assert store.task(task['id'])['status']=='cancelled'
        assert not manager.file_path(task['id']).exists()
        await manager.stop()
    asyncio.run(scenario())


def test_source_concurrency_is_bounded_and_event_loop_responsive(tmp_path):
    async def scenario():
        fake=DemoPlugin(Store(tmp_path));active=0;peak=0;lock=threading.Lock()
        def slow():
            nonlocal active,peak
            with lock:active+=1;peak=max(active,peak)
            time.sleep(.05)
            with lock:active-=1
        fake.slow=slow
        service=AggregatorService(fake.store,{'demo':fake})
        calls=[asyncio.create_task(service.call('demo','slow')) for _ in range(6)]
        await asyncio.sleep(.01)
        assert not calls[0].done()
        await asyncio.gather(*calls)
        assert peak==2
    asyncio.run(scenario())


def test_copy_parsing_pagination_and_image_order(tmp_path, monkeypatch):
    plugin=CopyPlugin(Store(tmp_path));calls=[]
    def get(path,**params):
        calls.append((path,params))
        if path.startswith('comic2/'):
            return {'comic':{'path_word':'book','name':'标题','author':[{'name':'作者'}]},'groups':{'default':{'path_word':'default','name':'正篇'}}}
        if '/group/' in path:
            return {'list':[{'uuid':str(params['offset']),'name':'章节'}],'total':2}
        if '/chapter2/' in path:
            raise ComicApiError('not found',404)
        return {'chapter':{'contents':[{'url':'second'},{'url':'first'}],'words':[2,1]}}
    monkeypatch.setattr(plugin,'_get',get)
    assert len(plugin.detail('book')['chapters'])==2
    assert plugin.pages('book','chapter')==['first','second']
    count=len(calls)
    assert plugin.pages('book','chapter')==['first','second'] and len(calls)==count


def test_library_source_isolation_and_missing_key(tmp_path):
    store = Store(tmp_path)
    store.save_book('one', 'same', {'title': 'First'})
    store.save_book('two', 'same', {'title': 'Second'})
    assert len(Store(tmp_path).books()) == 2
    (tmp_path / 'credentials.key').unlink()
    with pytest.raises(RuntimeError, match='Missing credentials.key'):
        Store(tmp_path)


def test_source_settings_persist_and_replace_adapter(client):
    service = client.app.state.service
    old = CopyPlugin(client.app.state.store)
    service.sources['copy'] = old
    manifest = client.get('/api/sources').json()['sources'][-1]
    assert manifest['settings_fields'][0]['name'] == 'api_base'
    assert 'login' not in manifest['capabilities']
    path = '/api/sources/copy/settings'
    assert client.put(path, json={'api_base': 'https://mirror.example/api/v3/'}).status_code == 200
    replacement = service.sources['copy']
    assert replacement.base == 'https://mirror.example/api/v3'
    assert old.base != replacement.base
    assert replacement.client is old.client
    assert replacement._chapter_clock is old._chapter_clock
    assert CopyPlugin(client.app.state.store).base == replacement.base
    assert client.put(path, json={'api_base': 'https://user:password@host/api'}).status_code == 422
    assert client.put(path, json={'unknown': 'value'}).status_code == 422
    assert client.put('/api/sources/demo/settings', json={}).status_code == 400
    assert client.put(path, json={'api_base': ''}).status_code == 200
    assert service.sources['copy'].base == old.default_base


def test_partial_search_retains_success(tmp_path):
    store = Store(tmp_path)
    good, bad = DemoPlugin(store), DemoPlugin(store)
    def fail(*args):
        raise ComicApiError('限流', 429, 'rate_limited')
    bad.search = fail
    service = AggregatorService(store, {'good': good, 'bad': bad})
    result = asyncio.run(service.aggregate_search('book'))
    assert result['all_results']['good']
    assert result['errors']['bad']['code'] == 'rate_limited'
    assert result['items'] == result['all_results']['good']


def test_mixed_search_ranks_across_sources(tmp_path):
    store = Store(tmp_path)
    first, second = DemoPlugin(store), DemoPlugin(store)
    first.search = lambda *args: [{'id': '1', 'title': '其他漫画'}, {'id': '2', 'title': '夏目友人帐 番外'}]
    second.search = lambda *args: [{'id': '1', 'title': '夏目友人帐'}, {'id': '2', 'title': '夏日友人'}]
    service = AggregatorService(store, {'first': first, 'second': second})
    result = asyncio.run(service.aggregate_search('夏目友人帐'))
    assert [(r['source'], r['id']) for r in result['items'][:2]] == [('second', '1'), ('first', '2')]
    assert result['best_match'] == result['items'][0]
    assert len(result['items']) == 4
    variants = service.rank_results('ＡＢＣ', [{'title': 'ABC 外传'}, {'title': 'a-b c'}, {'title': 'ABC'}])
    assert [v['title'] for v in variants] == ['a-b c', 'ABC', 'ABC 外传']


def test_cancelled_caller_keeps_thread_permit(tmp_path):
    async def scenario():
        fake = DemoPlugin(Store(tmp_path))
        release, entered = threading.Event(), threading.Event()
        active = 0
        lock = threading.Lock()
        def slow():
            nonlocal active
            with lock:
                active += 1
                if active == 2:
                    entered.set()
            release.wait(3)
        fake.slow = slow
        service = AggregatorService(fake.store, {'demo': fake})
        calls = [asyncio.create_task(service.call('demo', 'slow')) for _ in range(2)]
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            calls[0].cancel()
            await asyncio.gather(calls[0], return_exceptions=True)
            third = asyncio.create_task(service.call('demo', 'slow'))
            calls.append(third)
            await asyncio.sleep(.04)
            assert active == 2 and not third.done()
        finally:
            release.set()
            await asyncio.gather(*calls, return_exceptions=True)
        with pytest.raises(ComicApiError) as error:
            await service.call('demo', 'nonexistent')
        assert error.value.code == 'unsupported'
    asyncio.run(scenario())
