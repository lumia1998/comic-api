import sys
sys.path.append(".")
from src.clients.bika import BikaClient

client = BikaClient()
print("--- 哔咔网络诊断工具 ---")
print(f"当前本地保存的 Token: {client.authorization}")

if not client.authorization:
    print("【提示】本地未发现 Token，请先在网页绑定账号。")
    sys.exit(1)

print("正在向哔咔发送「原神」检索请求...")
try:
    res = client.search("原神")
    print("【成功】接口通信与数据解析完全正常！")
    print(f"搜索到漫画数量: {len(res)}")
    if res:
        print(f"第一条漫画完美格式结果: {res[0]}")
except Exception as e:
    print(f"【请求失败】错误详情: {e}")
