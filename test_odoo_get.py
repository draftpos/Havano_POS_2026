import urllib.request
import json

def test():
    url = 'http://192.168.1.181:8069/api/v1/products'
    req = urllib.request.Request(url, headers={'X-API-Key': 'd8616c8792019a16f3d994bb4043b17fb32a26c4'})
    res = urllib.request.urlopen(req).read().decode()
    data = json.loads(res)
    items = data.get("items", data.get("data", {}).get("items", []))
    for item in items:
        if item.get("default_code") == "ENV-TEST-01":
            print(f"Found ENV-TEST-01 with ID: {item.get('id')}")
            return
    print("Not found in first page")

test()
