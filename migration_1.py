from database.db import get_connection
from models.sale import migrate_alter

with get_connection() as conn:
    migrate_alter(conn)

print("Migration done.")