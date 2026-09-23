import urllib.request
import urllib.parse
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

base = "https://backoffice.havano.pro"
token = "YWJjNEBnbWFpbC5jb206SjFtNDkzMHdyMQ=="
hdr = {"Authorization": f"token {token}", "Accept": "application/json"}

# Query items with variants or specific filters
filters_to_test = [
    [["Item", "has_variants", "=", 1]],
    [["Item", "variant_of", "is", "set"]],
    [["Item", "item_code", "like", "%NK%"]],
    [["Item", "item_name", "like", "%Nike%"]],
]

for f in filters_to_test:
    params = urllib.parse.urlencode({
        "fields": json.dumps(["name", "item_code", "item_name", "has_variants", "variant_of"]),
        "filters": json.dumps(f),
        "limit_page_length": 10
    })
    url = f"{base}/api/resource/Item?{params}"
    req = urllib.request.Request(url, headers=hdr, method="GET")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            items = data.get("data", [])
            print(f"Filter {f} -> {len(items)} items: {items}")
    except Exception as e:
        print(f"Filter {f} -> Error: {e}")
