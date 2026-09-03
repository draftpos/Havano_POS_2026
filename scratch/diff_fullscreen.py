# -*- coding: utf-8 -*-
with open('views/dialogs/restaurant_settings_dialog.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_init = '''class RestaurantSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Restaurant Management")
        self.setMinimumSize(960, 720)
        self.setModal(True)'''

new_init = '''class RestaurantSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Restaurant Management")
        self.setMinimumSize(960, 720)
        self.setWindowState(Qt.WindowMaximized)
        self.setModal(True)'''

if old_init in code:
    code = code.replace(old_init, new_init)
else:
    print("Could not find old_init!")

with open('views/dialogs/restaurant_settings_dialog.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Done patching restaurant_settings_dialog.py')
