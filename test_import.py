import traceback
try:
    from views.main_window import MainWindow
    print("OK")
except Exception as e:
    traceback.print_exc()
