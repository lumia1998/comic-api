import random
import uuid
try:
    from curl_cffi import requests
except ImportError:
    import requests
    # Monkeypatch requests.Session to pop 'impersonate'
    _orig_request = requests.Session.request
    def _patched_request(self, method, url, **kwargs):
        kwargs.pop("impersonate", None)
        return _orig_request(self, method, url, **kwargs)
    requests.Session.request = _patched_request


def generate_android_user_agent(device_id: str = None) -> str:
    """对应 state.ts 生成符合 Android 规律的 User-Agent"""
    if not device_id:
        device_id = "".join(random.choices("0123456789abcdef", k=16))
    
    android_versions = ["10", "11", "12", "13", "14", "15"]
    chrome_versions = [
        "114.0.5735.196",
        "116.0.5845.172",
        "118.0.5993.111",
        "119.0.6045.194",
        "120.0.6099.230",
        "121.0.6167.178",
        "122.0.6261.119",
        "123.0.6312.118",
        "124.0.6367.179",
        "125.0.6422.165",
    ]
    build_codes = [
        "TQ1A.230305.002",
        "UP1A.231005.007",
        "UQ1A.240205.002",
        "AP1A.240405.002",
    ]

    android = random.choice(android_versions)
    chrome = random.choice(chrome_versions)
    build = random.choice(build_codes)

    return f"Mozilla/5.0 (Linux; Android {android}; {device_id} Build/{build}; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/{chrome} Mobile Safari/537.36"

class BaseClient:
    def __init__(self, impersonate: str = "chrome110"):
        self.impersonate = impersonate
        self.device_id = "".join(random.choices("0123456789abcdef", k=16))
        self.ua = generate_android_user_agent(self.device_id)
        self.session = requests.Session()
        
    def request(self, method: str, url: str, **kwargs):
        # 强制添加 impersonate 伪装 TLS
        if "impersonate" not in kwargs:
            kwargs["impersonate"] = self.impersonate
            
        headers = kwargs.get("headers", {})
        if "user-agent" not in {k.lower() for k in headers.keys()}:
            headers["user-agent"] = self.ua
        kwargs["headers"] = headers
        
        return self.session.request(method, url, **kwargs)
