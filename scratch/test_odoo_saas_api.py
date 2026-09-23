import urllib.request
import urllib.error
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

base_url = "https://backoffice.havano.pro"
login_url = f"{base_url}/saas_api/login"

# Test logins with database or empty database
for db in ["", "havano", "odoo", "backoffice"]:
    payload = json.dumps({
        "db": db,
        "usr": "abc4@gmail.com",
        "pwd": "Admin@123",
        "timezone": ""
    }).encode("utf-8")

    req = urllib.request.Request(
        login_url, data=payload, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            print(f"SUCCESS login with db='{db}': keys={list(data.keys())}")
            token = data.get("token")
            # Now call /saas_api/get_products
            prod_url = f"{base_url}/saas_api/get_products"
            prod_req = urllib.request.Request(
                prod_url, data=json.dumps({"db": db}).encode('utf-8'),
                headers={"Content-Type": "application/json", "Accept": "application/json", "Authorization": token},
                method="POST"
            )
            with urllib.request.urlopen(prod_req, context=ctx, timeout=15) as presp:
                pdata = json.loads(presp.read().decode())
                print(f"Products response keys: {list(pdata.keys())}")
                # check items
                msg = pdata.get("message")
                items = msg if isinstance(msg, list) else (msg.get("products") if isinstance(msg, dict) else [])
                print(f"Items found: {len(items)}")
                for it in items[:5]:
                    print("  Item:", it.get("name") or it.get("item_code"), "variants:", bool(it.get("variants")))
            break
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:150]
        print(f"HTTP {e.code} for db='{db}': {body}")
    except Exception as e:
        print(f"ERR for db='{db}': {e}")
