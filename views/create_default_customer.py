# #!/usr/bin/env python
# """
# Standalone script to create Default customer on first login.
# This script properly integrates with the Frappe sync system.

# Usage:
#     python create_default_customer.py
# """

# import sys
# import os
# sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

# from database.db import get_connection
# from datetime import datetime
# import json
# import urllib.request
# import urllib.error

# # Import the existing services that your sync system uses
# def _get_credentials_from_service():
#     """Use the same credentials service as sync_customers()"""
#     try:
#         from services.credentials import get_credentials
#         return get_credentials()
#     except ImportError:
#         return "", ""
#     except Exception:
#         return "", ""

# def _get_host_from_service():
#     """Use the same site_config service as sync_customers()"""
#     try:
#         from services.site_config import get_host
#         return get_host()
#     except ImportError:
#         return None
#     except Exception:
#         return None

# def create_default_customer():
#     """Create Default customer with proper Frappe sync integration"""
    
#     conn = get_connection()
#     cursor = conn.cursor()
    
#     print("\n" + "="*60)
#     print("  CREATE DEFAULT CUSTOMER")
#     print("="*60)
#     print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
#     print("="*60 + "\n")
    
#     try:
#         # Step 1: Check if Default customer already exists
#         print("1. Checking if Default customer exists...")
#         cursor.execute("SELECT id, frappe_synced FROM [dbo].[customers] WHERE customer_name = 'Default'")
#         existing = cursor.fetchone()
        
#         if existing:
#             customer_id = existing[0]
#             frappe_synced = existing[1]
#             print(f"   ✅ Default customer already exists (ID: {customer_id})")
#             if frappe_synced:
#                 print(f"   ✅ Already synced with Frappe")
#             else:
#                 print(f"   ⚠️  Exists but not synced with Frappe - will trigger sync")
#                 # Trigger sync for existing unsynced customer
#                 sync_result = _trigger_frappe_sync(cursor, conn, customer_id)
#                 if sync_result:
#                     print(f"   ✅ Successfully synced existing customer!")
#                 else:
#                     print(f"   ⚠️  Will retry sync later via background thread")
#             print("\n" + "="*60)
#             print("  CUSTOMER READY")
#             print("="*60 + "\n")
#             conn.close()
#             return True
        
#         # Step 2: Get company defaults for warehouse/cost center mappings
#         print("2. Fetching company defaults...")
#         cursor.execute("""
#             SELECT TOP 1 
#                 [server_warehouse],
#                 [server_cost_center],
#                 [server_company_currency],
#                 [email],
#                 [phone]
#             FROM [dbo].[company_defaults]
#         """)
        
#         company = cursor.fetchone()
        
#         if not company:
#             print("   ⚠️  No company defaults found! Using defaults...")
#             warehouse_name = None
#             cost_center_name = None
#             currency = 'USD'
#             email = 'no-email@default.com'
#             phone = '0000000000'
#         else:
#             warehouse_name = company[0]
#             cost_center_name = company[1]
#             currency = company[2] or 'USD'
#             email = company[3] or 'no-email@default.com'
#             phone = company[4] or '0000000000'
#             print(f"   ✅ Company defaults loaded")
#             print(f"      Currency: {currency}")
#             print(f"      Email: {email}")
#             print(f"      Phone: {phone}")
        
#         # Step 3: Find warehouse ID
#         print("\n3. Linking warehouse...")
#         warehouse_id = None
#         warehouse_name_final = None
#         if warehouse_name:
#             cursor.execute("SELECT TOP 1 id, name FROM [dbo].[warehouses] WHERE name = ?", (warehouse_name,))
#             wh = cursor.fetchone()
#             if wh:
#                 warehouse_id = wh[0]
#                 warehouse_name_final = wh[1]
#                 print(f"   ✅ Warehouse: {warehouse_name_final} (ID: {warehouse_id})")
#             else:
#                 print(f"   ⚠️  Warehouse '{warehouse_name}' not found")
#                 cursor.execute("SELECT TOP 1 id, name FROM [dbo].[warehouses] ORDER BY id ASC")
#                 wh = cursor.fetchone()
#                 if wh:
#                     warehouse_id = wh[0]
#                     warehouse_name_final = wh[1]
#                     print(f"   ✅ Using fallback: {warehouse_name_final}")
        
#         # Step 4: Find cost center ID
#         print("\n4. Linking cost center...")
#         cost_center_id = None
#         cost_center_name_final = None
#         if cost_center_name:
#             cursor.execute("SELECT TOP 1 id, name FROM [dbo].[cost_centers] WHERE name = ?", (cost_center_name,))
#             cc = cursor.fetchone()
#             if cc:
#                 cost_center_id = cc[0]
#                 cost_center_name_final = cc[1]
#                 print(f"   ✅ Cost Center: {cost_center_name_final} (ID: {cost_center_id})")
#             else:
#                 print(f"   ⚠️  Cost center '{cost_center_name}' not found")
#                 cursor.execute("SELECT TOP 1 id, name FROM [dbo].[cost_centers] ORDER BY id ASC")
#                 cc = cursor.fetchone()
#                 if cc:
#                     cost_center_id = cc[0]
#                     cost_center_name_final = cc[1]
#                     print(f"   ✅ Using fallback: {cost_center_name_final}")
        
#         # Step 5: Get price list
#         print("\n5. Getting price list...")
#         price_list_id = None
#         cursor.execute("SELECT TOP 1 id FROM [dbo].[price_lists] ORDER BY id ASC")
#         pl = cursor.fetchone()
#         if pl:
#             price_list_id = pl[0]
#             print(f"   ✅ Price list ID: {price_list_id}")
        
#         # Step 6: Get customer group
#         print("\n6. Getting customer group...")
#         customer_group_id = None
#         cursor.execute("SELECT TOP 1 id FROM [dbo].[customer_groups] ORDER BY id ASC")
#         cg = cursor.fetchone()
#         if cg:
#             customer_group_id = cg[0]
#             print(f"   ✅ Customer group ID: {customer_group_id}")
        
#         # Step 7: Create Default customer
#         print("\n7. Creating Default customer...")
        
#         cursor.execute("""
#             INSERT INTO [dbo].[customers] 
#                 (customer_name, customer_type, customer_group_id,
#                  custom_warehouse_id, custom_cost_center_id, default_price_list_id,
#                  custom_trade_name, custom_telephone_number, custom_email_address,
#                  custom_city, custom_house_no,
#                  balance, outstanding_amount, laybye_balance, 
#                  loyalty_points, frappe_synced)
#             OUTPUT INSERTED.id
#             VALUES (?, 'Individual', ?, ?, ?, ?, 
#                     'Default Trade', ?, ?,
#                     'Harare', '1',
#                     0, 0, 0, 0, 0)
#         """, (
#             'Default', customer_group_id, warehouse_id, cost_center_id, price_list_id,
#             phone, email
#         ))
        
#         customer_id = cursor.fetchone()[0]
#         conn.commit()
        
#         print(f"   ✅ Default customer created! (ID: {customer_id})")
        
#         # Step 8: Push to Frappe using existing services
#         print("\n8. Pushing to Frappe...")
#         push_success = _push_using_services(cursor, conn, customer_id, 
#                                             warehouse_name_final, cost_center_name_final,
#                                             currency, email, phone)
        
#         if push_success:
#             print(f"   ✅ Successfully pushed to Frappe!")
#         else:
#             print(f"   ⚠️  Will be synced when Frappe is available")
        
#         print("\n" + "="*60)
#         print("  ✅ DEFAULT CUSTOMER CREATED SUCCESSFULLY")
#         print("="*60)
#         print("\n📝 Summary:")
#         print(f"   • Customer ID: {customer_id}")
#         print(f"   • Name: Default")
#         print(f"   • Pushed to Frappe: {'Yes' if push_success else 'No (will retry)'}")
#         print("\n" + "="*60 + "\n")
        
#         conn.close()
#         return True
        
#     except Exception as e:
#         print(f"\n❌ Error: {e}")
#         import traceback
#         traceback.print_exc()
#         conn.rollback()
#         conn.close()
#         return False


# def _push_using_services(cursor, conn, customer_id, warehouse_name, cost_center_name, currency, email, phone):
#     """
#     Push Default customer to Frappe using the SAME services as sync_customers()
#     - Gets credentials from services.credentials.get_credentials()
#     - Gets host URL from services.site_config.get_host()
#     """
    
#     # Use the same credential service as sync_customers()
#     api_key, api_secret = _get_credentials_from_service()
    
#     # Use the same host service as sync_customers()
#     base_url = _get_host_from_service()
    
#     if not api_key or not api_secret:
#         print(f"   ⚠️  No API credentials available from credentials service")
#         return False
    
#     if not base_url:
#         print(f"   ⚠️  No Frappe host configured in site_config")
#         return False
    
#     print(f"   📍 Using host: {base_url}")
#     print(f"   🔑 Using API key: {api_key[:8]}...")
    
#     # Prepare payload for Frappe API
#     payload = {
#         "customer_name": "Default",
#         "customer_type": "Individual",
#         "customer_group": "All Customer Groups",
#         "custom_telephone_number": phone or "0000000000",
#         "custom_email_address": email or "no-email@default.com",
#         "custom_city": "Harare",
#         "default_warehouse": warehouse_name or "",
#         "default_cost_center": cost_center_name or "",
#         "default_price_list": "Standard Selling",
#         "custom_trade_name": "Default Trade",
#         "custom_house_no": "1",
#         "custom_street": "Unknown",
#         "custom_customer_address": "N/A",
#         "custom_province": "N/A",
#         "is_active": 1
#     }
    
#     # Remove empty values
#     payload = {k: v for k, v in payload.items() if v}
    
#     # Use the same API endpoint as your sync expects
#     url = f"{base_url}/api/method/saas_api.www.api.create_customer"
    
#     print(f"   📤 POST {url}")
#     print(f"   📦 Customer: Default")
    
#     body = json.dumps(payload).encode()
#     req = urllib.request.Request(url, data=body, method="POST")
#     req.add_header("Authorization", f"token {api_key}:{api_secret}")
#     req.add_header("Content-Type", "application/json")
#     req.add_header("Accept", "application/json")
    
#     try:
#         with urllib.request.urlopen(req, timeout=30) as resp:
#             result = json.loads(resp.read().decode())
#             if result.get("data"):
#                 print(f"   ✅ Success! Frappe ID: {result['data'].get('name', 'Unknown')}")
#                 # Mark as synced
#                 cursor.execute("UPDATE customers SET frappe_synced = 1 WHERE id = ?", (customer_id,))
#                 conn.commit()
#                 return True
#             else:
#                 print(f"   ⚠️  Unexpected response: {result}")
#                 return False
#     except urllib.error.HTTPError as e:
#         error_body = e.read().decode(errors='replace')
#         print(f"   ❌ HTTP {e.code}: {error_body[:200]}")
#         return False
#     except Exception as e:
#         print(f"   ❌ Error: {e}")
#         return False


# def _trigger_frappe_sync(cursor, conn, customer_id):
#     """Trigger Frappe sync for existing unsynced customer using the same services"""
    
#     # Use the same services as sync_customers()
#     api_key, api_secret = _get_credentials_from_service()
#     base_url = _get_host_from_service()
    
#     if not api_key or not api_secret:
#         print(f"   ⚠️  No API credentials available")
#         return False
    
#     if not base_url:
#         print(f"   ⚠️  No Frappe host configured")
#         return False
    
#     # Get customer details with linked names
#     cursor.execute("""
#         SELECT 
#             c.customer_name,
#             c.custom_telephone_number,
#             c.custom_email_address,
#             c.custom_city,
#             w.name as warehouse_name,
#             cc.name as cost_center_name
#         FROM customers c
#         LEFT JOIN warehouses w ON w.id = c.custom_warehouse_id
#         LEFT JOIN cost_centers cc ON cc.id = c.custom_cost_center_id
#         WHERE c.id = ?
#     """, (customer_id,))
    
#     customer = cursor.fetchone()
#     if not customer:
#         print(f"   ❌ Customer not found")
#         return False
    
#     # Prepare payload
#     payload = {
#         "customer_name": customer[0],
#         "customer_type": "Individual",
#         "customer_group": "All Customer Groups",
#         "custom_telephone_number": customer[1] or "0000000000",
#         "custom_email_address": customer[2] or "no-email@default.com",
#         "custom_city": customer[3] or "Harare",
#         "default_warehouse": customer[4] or "",
#         "default_cost_center": customer[5] or "",
#         "default_price_list": "Standard Selling",
#         "custom_trade_name": "Default Trade",
#         "custom_house_no": "1",
#         "custom_street": "Unknown",
#         "custom_customer_address": "N/A",
#         "custom_province": "N/A",
#         "is_active": 1
#     }
    
#     payload = {k: v for k, v in payload.items() if v}
    
#     url = f"{base_url}/api/method/saas_api.www.api.create_customer"
    
#     print(f"   📤 POST {url}")
#     print(f"   📦 Customer: {customer[0]}")
    
#     body = json.dumps(payload).encode()
#     req = urllib.request.Request(url, data=body, method="POST")
#     req.add_header("Authorization", f"token {api_key}:{api_secret}")
#     req.add_header("Content-Type", "application/json")
#     req.add_header("Accept", "application/json")
    
#     try:
#         with urllib.request.urlopen(req, timeout=30) as resp:
#             result = json.loads(resp.read().decode())
#             if result.get("data"):
#                 print(f"   ✅ Success! Frappe ID: {result['data'].get('name', 'Unknown')}")
#                 cursor.execute("UPDATE customers SET frappe_synced = 1 WHERE id = ?", (customer_id,))
#                 conn.commit()
#                 return True
#             return False
#     except Exception as e:
#         print(f"   ❌ Error: {e}")
#         return False


# def get_default_customer():
#     """Get the Default customer"""
#     conn = get_connection()
#     try:
#         cursor = conn.cursor()
#         cursor.execute("""
#             SELECT id, customer_name, custom_warehouse_id, custom_cost_center_id,
#                    balance, outstanding_amount, frappe_synced
#             FROM customers 
#             WHERE customer_name = 'Default'
#         """)
#         customer = cursor.fetchone()
        
#         if customer:
#             return {
#                 'id': customer[0],
#                 'customer_name': customer[1],
#                 'custom_warehouse_id': customer[2],
#                 'custom_cost_center_id': customer[3],
#                 'balance': float(customer[4] or 0),
#                 'outstanding_amount': float(customer[5] or 0),
#                 'frappe_synced': bool(customer[6])
#             }
#         return None
#     except Exception as e:
#         print(f"Error: {e}")
#         return None
#     finally:
#         conn.close()


# if __name__ == "__main__":
#     success = create_default_customer()
#     sys.exit(0 if success else 1)