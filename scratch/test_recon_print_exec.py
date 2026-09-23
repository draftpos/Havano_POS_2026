import sys
import os

sys.path.insert(0, os.path.abspath('.'))

from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from services.printing_service import printing_service

test_multi_recon = {
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
        {'method': 'ACC TEST NO CURR', 'currency': 'USD', 'expected': 2.00, 'counted': 1.00, 'variance': -1.00},
        {'method': 'CASH ZIG', 'currency': 'ZWG', 'expected': 175.00, 'counted': 170.00, 'variance': -5.00}
    ],
    'cashiers': [
        {
            'cashier_id': 1,
            'cashier_name': 'admin',
            'total_sales': 177.0,
            'transactions': 2,
            'rows': [
                {'method': 'ACC TEST NO CURR', 'currency': 'USD', 'expected': 2.00, 'counted': 1.00, 'variance': -1.00},
                {'method': 'CASH ZIG', 'currency': 'ZWG', 'expected': 175.00, 'counted': 170.00, 'variance': -5.00}
            ]
        }
    ]
}

totals = [
    {'method': 'ACC TEST NO CURR', 'currency': 'USD', 'expected': 2.0, 'actual': 1.0, 'variance': -1.0},
    {'method': 'CASH ZIG', 'currency': 'ZWG', 'expected': 175.0, 'actual': 170.0, 'variance': -5.0}
]

print("Testing print_shift_reconciliation execution with multi-currency payload...")
res = printing_service.print_shift_reconciliation(
    totals=totals,
    reconciliation_data=test_multi_recon,
    printer_name="(None)"
)
print(f"Result: {res}")
print("Test completed successfully without NameError or exceptions!")
