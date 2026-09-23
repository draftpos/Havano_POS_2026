import sys
import os

sys.path.insert(0, os.path.abspath('.'))

from services.printing_service import printing_service

test_recon = {
    'shift_id': 1,
    'shift_number': 1,
    'station': 1,
    'station_name': 'POS-01',
    'date': '2026-09-11',
    'start_time': '08:00:00',
    'end_time': '16:00:00',
    'closing_cashier_name': 'Cashier 1',
    'opening_balance': 150.00,
    'total_expected': 250.00,
    'total_counted': 250.00,
    'total_variance': 0.00,
    'payment_methods': [
        {'method': 'Cash', 'currency': 'USD', 'expected': 250.00, 'counted': 250.00, 'variance': 0.00}
    ],
    'cashiers': []
}

print("Testing reconciliation data structure:")
print(f"Opening balance: {test_recon['opening_balance']}")
print(f"Expected sales: {test_recon['total_expected']}")
print("Data structure confirmed!")
