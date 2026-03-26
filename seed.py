import logging
from database.db import get_connection

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("cleanup_service")

def delete_all_sales_data():
    """
    Deletes all local sales orders, order items, and payment entry sync logs
    to allow for a clean restart of the synchronization process.
    """
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        log.info("Starting cleanup of sales and payment data...")

        # 1. Delete Payment Entry sync logs
        # This clears the queue of failed 417 errors you are seeing
        cur.execute("DELETE FROM laybye_payment_entries")
        log.info("Cleared 'laybye_payment_entries' table.")

        # 2. Delete Sales Order Items first (due to Foreign Key constraints)
        cur.execute("DELETE FROM sales_order_item")
        log.info("Cleared 'sales_order_item' table.")

        # 3. Delete the main Sales Orders
        cur.execute("DELETE FROM sales_order")
        log.info("Cleared 'sales_order' table.")

        # Optional: Reset Identity counters to 1
        cur.execute("DBCC CHECKIDENT ('sales_order', RESEED, 0)")
        cur.execute("DBCC CHECKIDENT ('laybye_payment_entries', RESEED, 0)")

        conn.commit()
        log.info("✅ Successfully deleted all local records. You can now restart the app.")

    except Exception as e:
        conn.rollback()
        log.error(f"❌ Cleanup failed: {str(e)}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    delete_all_sales_data() 