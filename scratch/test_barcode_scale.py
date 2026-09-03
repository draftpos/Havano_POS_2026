import sys
import os
from pathlib import Path

# Add project root to sys.path so we can import from views
sys.path.insert(0, str(Path(__file__).parent.parent))

from views.main_window import decode_weight_barcode

def run_tests():
    print("Running barcode decoding tests...")
    
    # We will mock the database call in decode_weight_barcode by monkeypatching
    import views.main_window
    original_get_connection = None
    try:
        from database.db import get_connection
        original_get_connection = get_connection
    except ImportError:
        pass
        
    class MockCursor:
        def __init__(self, setting_value):
            self.setting_value = setting_value
        def execute(self, query):
            pass
        def fetchone(self):
            if self.setting_value is None: return None
            return (self.setting_value,)
            
    class MockConnection:
        def __init__(self, setting_value):
            self.setting_value = setting_value
        def cursor(self):
            return MockCursor(self.setting_value)
        def close(self):
            pass

    def mock_get_conn_12(): return MockConnection("12-digit (DDPPPPPWWWWC)")
    def mock_get_conn_13(): return MockConnection("13-digit (DDPPPPPCWWWWC)")
    def mock_get_conn_legacy(): return MockConnection("Weight Based Scale")
    def mock_get_conn_none(): return MockConnection("No Scale")

    # Helper to test
    def test_case(mock_conn_func, barcode, expected_code, expected_weight):
        # Override the database connection locally
        sys.modules['database.db'].get_connection = mock_conn_func
        code, weight = decode_weight_barcode(barcode)
        assert code == expected_code, f"Expected code {expected_code}, got {code} for barcode {barcode}"
        assert weight == expected_weight, f"Expected weight {expected_weight}, got {weight} for barcode {barcode}"

    print("Testing 12-digit format...")
    # DD PPPPP WWWW C
    # 20 12345 0500 1 -> Code: 2012345, Weight: 0500 -> 0.5kg
    test_case(mock_get_conn_12, "201234505001", "2012345", 0.5)
    
    # 12-digit invalid length
    test_case(mock_get_conn_12, "20123450500", None, None)
    
    print("Testing 13-digit format...")
    # DD PPPPP C WWWW C
    # 20 12345 6 0500 1 -> Code: 20123456, Weight: 0500 -> 0.5kg
    test_case(mock_get_conn_13, "2012345605001", "20123456", 0.5)
    
    # 13-digit invalid length
    test_case(mock_get_conn_13, "201234560500", None, None)

    print("Testing legacy 13-digit format...")
    # DD PPPPP WWWWW C
    # 20 12345 00500 1 -> Code: 2012345, Weight: 00500 -> 0.5kg
    test_case(mock_get_conn_legacy, "2012345005001", "2012345", 0.5)
    
    print("Testing No Scale format...")
    test_case(mock_get_conn_none, "201234505001", None, None)
    
    print("Testing invalid characters...")
    test_case(mock_get_conn_12, "201234A05001", None, None)
    test_case(mock_get_conn_12, "", None, None)

    print("All unit tests passed.")

    if original_get_connection:
        sys.modules['database.db'].get_connection = original_get_connection

if __name__ == "__main__":
    run_tests()
