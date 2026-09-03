try:
    from services.sales_order_print import print_laybye_deposit
    print("Import successful")
except Exception as e:
    print(f"Import failed: {e}")
