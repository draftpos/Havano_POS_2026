from services.user_sync_service import sync_users
from models.user import get_all_users

print("Starting sync_users()...")
res = sync_users()
print("\n--- SYNC RESULT ---")
print(res)

print("\n--- SYNCED USERS ---")
users = get_all_users()
for u in users:
    print(f"User: {u['username']} | Role: {u['role']} | Warehouse: {u['warehouse']} | Company (Branch): {u['company']}")
