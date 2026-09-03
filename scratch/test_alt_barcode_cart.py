import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

def run_tests():
    print("Running Alternative Barcode Cart Integration Tests...")

    # We will mock the database and parent window structures to test _inline_commit_query and price resolution
    class MockConnection:
        def __init__(self, barcode_row, price_rows):
            self.barcode_row = barcode_row
            self.price_rows = price_rows

        def cursor(self):
            class MockCursor:
                def __init__(self, parent):
                    self.parent = parent
                def execute(self, query, params=None):
                    self.query = query
                    self.params = params
                def fetchone(self):
                    if "product_barcodes" in self.query:
                        return self.parent.barcode_row
                    return None
                def fetchall(self):
                    if "item_prices" in self.query:
                        return self.parent.price_rows
                    return []
            return MockCursor(self)
        def close(self):
            pass

    # Mock product model functions
    class MockProductModel:
        @staticmethod
        def get_product_by_part_no(part_no):
            return {
                "id": 42,
                "part_no": "TEST-PROD",
                "name": "Test Product",
                "uom": "Nos",
                "price": 10.0
            }

    # Monkeypatch get_connection and get_product_by_part_no
    import database.db
    import models.product
    
    # Store originals
    orig_conn = getattr(database.db, "get_connection", None)
    orig_get_prod = getattr(models.product, "get_product_by_part_no", None)

    # Let's create a Mock MainWindow to test _inline_commit_query
    class MockMainWindow:
        def __init__(self, db_conn):
            self._inline_row = 0
            self.invoice_table = self.MockTable()
            self._block_signals = False
            self._selected_customer = {"price_list_name": "Standard Selling"}
            self.db_conn = db_conn
            self.added_items = []

        class MockTable:
            def rowCount(self):
                return 0

        def _close_inline_search(self):
            pass

        def _get_active_price_list(self):
            return "Standard Selling"

        def _is_template_product(self, product):
            return False

        def _pick_product_uom_and_price(self, product, barcode_uom=None):
            # We import and execute the actual methods under test!
            from views.main_window import POSView
            # Bind the actual methods to our mock instance
            return POSView._pick_product_uom_and_price.__get__(self)(product, barcode_uom)

        def _resolve_price_for_product(self, product, barcode_uom=None):
            from views.main_window import POSView
            return POSView._resolve_price_for_product.__get__(self)(product, barcode_uom)

        def _get_price_rows_for_list(self, part_no, price_list):
            # Mock get_connection behavior
            database.db.get_connection = lambda: self.db_conn
            from views.main_window import POSView
            return POSView._get_price_rows_for_list.__get__(self)(part_no, price_list)

        def _add_product_to_invoice(self, name, price, part_no, product_id, uom, stock=None):
            self.added_items.append({
                "name": name,
                "price": price,
                "part_no": part_no,
                "product_id": product_id,
                "uom": uom
            })

    try:
        models.product.get_product_by_part_no = MockProductModel.get_product_by_part_no

        print("\nCase 1: Scanning alternative barcode maps to Box UOM")
        # Alternative barcode "7652686879" -> TEST-PROD, Box UOM
        mock_db = MockConnection(
            barcode_row=("TEST-PROD", "Box"),
            price_rows=[("Nos", 10.0), ("Box", 120.0)]
        )
        database.db.get_connection = lambda: mock_db
        
        mw = MockMainWindow(mock_db)
        
        # We call the actual method under test
        from views.main_window import POSView
        POSView._inline_commit_query.__get__(mw)("7652686879")
        
        # Verify the item is resolved and added directly with the Box UOM and Box Price!
        assert len(mw.added_items) == 1, "Should have added one item to the cart"
        added = mw.added_items[0]
        assert added["uom"] == "Box", f"Expected Box UOM, got {added['uom']}"
        assert added["price"] == 120.0, f"Expected price 120.0, got {added['price']}"
        print("Success: Item loaded directly with UOM 'Box' bypassing picker dialog!")

    finally:
        # Restore originals
        if orig_conn:
            database.db.get_connection = orig_conn
        if orig_get_prod:
            models.product.get_product_by_part_no = orig_get_prod

    print("\nAll integration test cases passed!")

if __name__ == "__main__":
    run_tests()
