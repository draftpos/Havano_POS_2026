from database.db import get_connection
cur = get_connection().cursor()
cur.execute("IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='products' AND COLUMN_NAME='description') ALTER TABLE products ADD description NVARCHAR(MAX) NULL")
cur.connection.commit()
print("OK")
