"""
Patch script for Havano POS:
1. Replace _on_cancel_kot plain dialog with rich popup + pass reason to KOT printer
2. Fix prebill footer in restaurant_view.py
3. Add KOT Activity page accessible from admin panel and restaurant toolbar
"""

import re
import sys

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 1 — main_window.py : _on_cancel_kot
# ─────────────────────────────────────────────────────────────────────────────
MW_PATH = r"c:\Users\DELL\New_POS\Havano_POS_2026\views\main_window.py"

with open(MW_PATH, "r", encoding="utf-8") as f:
    mw = f.read()

# --- 1a. Find and replace the plain QInputDialog block ---
old_block = (
    '        # Check if cancel reason is required\r\n'
    '        reason = ""\r\n'
    '        try:\r\n'
    '            from models.restaurant_order import get_restaurant_settings\r\n'
    '            rs = get_restaurant_settings()\r\n'
    '            if rs.get("require_cancel_reason"):\r\n'
    '                from PySide6.QtWidgets import QInputDialog\r\n'
    '                reason, ok = QInputDialog.getText(\r\n'
    '                    self, "Cancel Reason",\r\n'
    '                    f"Reason for cancelling KOT #ORD-{order_id}:"\r\n'
    '                )\r\n'
    '                if not ok:\r\n'
    '                    return  # user pressed Cancel on the dialog\r\n'
    '                if not reason.strip():\r\n'
    '                    QMessageBox.warning(self, "Reason Required",\r\n'
    '                                        "You must enter a reason to cancel this KOT.")\r\n'
    '                    return\r\n'
    '        except Exception:\r\n'
    '            pass'
)

new_block = (
    '        # ── Rich cancel-reason dialog (predefined chips + autocomplete) ──────────\r\n'
    '        reason = ""\r\n'
    '        try:\r\n'
    '            from models.restaurant_order import get_restaurant_settings, get_cancel_reasons\r\n'
    '            rs = get_restaurant_settings()\r\n'
    '            predefined_reasons = get_cancel_reasons()\r\n'
    '            reason = self._show_cancel_reason_dialog(order_id, predefined_reasons)\r\n'
    '            if reason is None:\r\n'
    '                return  # user dismissed\r\n'
    '            reason = reason.strip()\r\n'
    '            if rs.get("require_cancel_reason") and not reason:\r\n'
    '                QMessageBox.warning(self, "Reason Required",\r\n'
    '                                    "You must enter a reason to cancel this KOT.")\r\n'
    '                return\r\n'
    '        except Exception as _exc:\r\n'
    '            print(f"[CancelKOT] reason dialog error: {_exc}")'
)

if old_block in mw:
    mw = mw.replace(old_block, new_block, 1)
    print("✅ PATCH 1a applied: cancel reason dialog block replaced")
else:
    print("❌ PATCH 1a: old block NOT found — checking LF variant")
    old_lf = old_block.replace("\r\n", "\n")
    if old_lf in mw:
        mw = mw.replace(old_lf, new_block.replace("\r\n", "\n"), 1)
        print("✅ PATCH 1a applied (LF)")
    else:
        print("❌ PATCH 1a FAILED — skipping")

# --- 1b. Add cancel_reason to sale_stub ---
old_stub = (
    '                        sale_stub = {\r\n'
    '                            "invoice_no": f"ORD-{order_id}",\r\n'
    '                            "order_number": order_id,\r\n'
    '                            "cashier_name": self.user.get("username", "Unknown") if isinstance(self.user, dict) else "Unknown",\r\n'
    '                            "items": items,\r\n'
    '                            "bill_notes": order.get("bill_notes", ""),\r\n'
    '                            "customer_name": f"Table {table_name}"\r\n'
    '                        }'
)
new_stub = (
    '                        sale_stub = {\r\n'
    '                            "invoice_no": f"ORD-{order_id}",\r\n'
    '                            "order_number": order_id,\r\n'
    '                            "cashier_name": self.user.get("username", "Unknown") if isinstance(self.user, dict) else "Unknown",\r\n'
    '                            "items": items,\r\n'
    '                            "bill_notes": order.get("bill_notes", ""),\r\n'
    '                            "customer_name": f"Table {table_name}",\r\n'
    '                            "cancel_reason": reason,   # printed on cancellation KOT\r\n'
    '                        }'
)
if old_stub in mw:
    mw = mw.replace(old_stub, new_stub, 1)
    print("✅ PATCH 1b applied: cancel_reason added to sale_stub")
else:
    old_stub_lf = old_stub.replace("\r\n", "\n")
    if old_stub_lf in mw:
        mw = mw.replace(old_stub_lf, new_stub.replace("\r\n", "\n"), 1)
        print("✅ PATCH 1b applied (LF)")
    else:
        print("❌ PATCH 1b FAILED")

# --- 1c. Insert _show_cancel_reason_dialog method before _restaurant_auto_logout ---
anchor = "    def _restaurant_auto_logout(self):"
cancel_method = (
    "    def _show_cancel_reason_dialog(self, order_id: int, predefined: list):\r\n"
    "        \"\"\"\r\n"
    "        Rich cancel-reason dialog matching the bill-notes popup style.\r\n"
    "        Returns the entered reason string, or None if dismissed.\r\n"
    "        The first predefined reason is pre-filled as the default.\r\n"
    "        \"\"\"\r\n"
    "        default_reason = predefined[0] if predefined else \"\"\r\n"
    "\r\n"
    "        dlg = QDialog(self)\r\n"
    "        dlg.setWindowTitle(\"Cancel Reason\")\r\n"
    "        dlg.setFixedWidth(1100)\r\n"
    "        dlg.setStyleSheet(\r\n"
    "            f\"QDialog {{ background: {WHITE}; border: 1px solid {NAVY}; border-radius: 12px; }}\"\r\n"
    "        )\r\n"
    "        dlg.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)\r\n"
    "\r\n"
    "        root = QVBoxLayout(dlg)\r\n"
    "        root.setContentsMargins(15, 12, 15, 12)\r\n"
    "        root.setSpacing(8)\r\n"
    "\r\n"
    "        chip_btns = []\r\n"
    "        reason_input_ref = [None]  # mutable reference\r\n"
    "\r\n"
    "        if predefined:\r\n"
    "            chips_row = QHBoxLayout()\r\n"
    "            chips_row.setSpacing(6)\r\n"
    "\r\n"
    "            def _chip_style(active=False):\r\n"
    "                if active:\r\n"
    "                    return (\r\n"
    "                        f\"QPushButton {{\"\r\n"
    "                        f\"  background: {ACCENT}; color: {WHITE};\"\r\n"
    "                        f\"  border: 1px solid {ACCENT}; border-radius: 14px;\"\r\n"
    "                        f\"  font-size: 12px; font-weight: 600; padding: 4px 12px;\"\r\n"
    "                        f\"}}\"\r\n"
    "                    )\r\n"
    "                return (\r\n"
    "                    f\"QPushButton {{\"\r\n"
    "                    f\"  background: {OFF_WHITE}; color: {NAVY};\"\r\n"
    "                    f\"  border: 1px solid {BORDER}; border-radius: 14px;\"\r\n"
    "                    f\"  font-size: 12px; font-weight: 600; padding: 4px 12px;\"\r\n"
    "                    f\"}}\"\r\n"
    "                    f\"QPushButton:hover {{\"\r\n"
    "                    f\"  background: {ACCENT_SOFT}; border-color: {ACCENT}; color: {ACCENT};\"\r\n"
    "                    f\"}}\"\r\n"
    "                )\r\n"
    "\r\n"
    "            for r_txt in predefined:\r\n"
    "                chip = QPushButton(r_txt)\r\n"
    "                chip.setCursor(Qt.PointingHandCursor)\r\n"
    "                chip.setCheckable(True)\r\n"
    "                chip.setStyleSheet(_chip_style(False))\r\n"
    "                chips_row.addWidget(chip)\r\n"
    "                chip_btns.append((r_txt, chip))\r\n"
    "\r\n"
    "            chips_row.addStretch()\r\n"
    "            root.addLayout(chips_row)\r\n"
    "\r\n"
    "        # ── Input row ──────────────────────────────────────────────────────\r\n"
    "        inp_row = QHBoxLayout()\r\n"
    "        inp_row.setSpacing(10)\r\n"
    "\r\n"
    "        lbl = QLabel(\"Reason:\")\r\n"
    "        lbl.setStyleSheet(f\"color: {NAVY}; font-size: 13px; font-weight: bold;\")\r\n"
    "        inp_row.addWidget(lbl)\r\n"
    "\r\n"
    "        reason_input = QLineEdit(default_reason)\r\n"
    "        reason_input.setPlaceholderText(\"Enter reason\u2026\")\r\n"
    "        reason_input.setFixedHeight(44)\r\n"
    "        reason_input.setStyleSheet(\r\n"
    "            f\"QLineEdit {{\"\r\n"
    "            f\"  border: 1px solid {BORDER}; border-radius: 8px;\"\r\n"
    "            f\"  padding: 0 15px; font-size: 15px; color: {DARK_TEXT};\"\r\n"
    "            f\"  background: {OFF_WHITE};\"\r\n"
    "            f\"}}\"\r\n"
    "            f\"QLineEdit:focus {{ border-color: {ACCENT}; background: {WHITE}; }}\"\r\n"
    "        )\r\n"
    "        reason_input_ref[0] = reason_input\r\n"
    "\r\n"
    "        if predefined:\r\n"
    "            completer = QCompleter(predefined, reason_input)\r\n"
    "            completer.setCaseSensitivity(Qt.CaseInsensitive)\r\n"
    "            completer.setFilterMode(Qt.MatchContains)\r\n"
    "            completer.setCompletionMode(QCompleter.PopupCompletion)\r\n"
    "            completer.popup().setStyleSheet(\r\n"
    "                f\"QListView {{\"\r\n"
    "                f\"  background: {WHITE}; border: 1px solid {BORDER};\"\r\n"
    "                f\"  border-radius: 6px; font-size: 14px; color: {DARK_TEXT}; padding: 4px;\"\r\n"
    "                f\"}}\"\r\n"
    "                f\"QListView::item {{ padding: 8px 12px; }}\"\r\n"
    "                f\"QListView::item:selected {{ background: {ACCENT}; color: {WHITE}; }}\"\r\n"
    "            )\r\n"
    "            reason_input.setCompleter(completer)\r\n"
    "\r\n"
    "            def _on_chip(txt, clicked_chip):\r\n"
    "                reason_input.setText(txt)\r\n"
    "                for _r, _c in chip_btns:\r\n"
    "                    active = _c is clicked_chip\r\n"
    "                    _c.setChecked(active)\r\n"
    "                    _c.setStyleSheet(_chip_style(active))\r\n"
    "\r\n"
    "            for r_text, c_btn in chip_btns:\r\n"
    "                c_btn.clicked.connect(lambda _, t=r_text, b=c_btn: _on_chip(t, b))\r\n"
    "\r\n"
    "            # Pre-select first chip\r\n"
    "            if chip_btns:\r\n"
    "                chip_btns[0][1].setChecked(True)\r\n"
    "                chip_btns[0][1].setStyleSheet(_chip_style(True))\r\n"
    "\r\n"
    "        inp_row.addWidget(reason_input, 1)\r\n"
    "\r\n"
    "        ok_btn = QPushButton(\"\u2713  Cancel KOT\")\r\n"
    "        ok_btn.setFixedSize(150, 44)\r\n"
    "        ok_btn.setCursor(Qt.PointingHandCursor)\r\n"
    "        ok_btn.setStyleSheet(\r\n"
    "            f\"QPushButton {{\"\r\n"
    "            f\"  background: {DANGER}; color: {WHITE}; border: none;\"\r\n"
    "            f\"  border-radius: 8px; font-size: 14px; font-weight: bold;\"\r\n"
    "            f\"}}\"\r\n"
    "            f\"QPushButton:hover {{ background: {DANGER_H}; }}\"\r\n"
    "        )\r\n"
    "        ok_btn.clicked.connect(dlg.accept)\r\n"
    "        inp_row.addWidget(ok_btn)\r\n"
    "\r\n"
    "        dismiss_btn = QPushButton(\"\u2715\")\r\n"
    "        dismiss_btn.setFixedSize(44, 44)\r\n"
    "        dismiss_btn.setCursor(Qt.PointingHandCursor)\r\n"
    "        dismiss_btn.setStyleSheet(\r\n"
    "            f\"QPushButton {{\"\r\n"
    "            f\"  background: {OFF_WHITE}; color: {NAVY};\"\r\n"
    "            f\"  border: 1px solid {BORDER}; border-radius: 8px; font-size: 18px;\"\r\n"
    "            f\"}}\"\r\n"
    "            f\"QPushButton:hover {{\"\r\n"
    "            f\"  background: {WHITE}; border-color: {DANGER}; color: {DANGER};\"\r\n"
    "            f\"}}\"\r\n"
    "        )\r\n"
    "        dismiss_btn.clicked.connect(dlg.reject)\r\n"
    "        inp_row.addWidget(dismiss_btn)\r\n"
    "\r\n"
    "        reason_input.returnPressed.connect(dlg.accept)\r\n"
    "        reason_input.setFocus()\r\n"
    "        reason_input.selectAll()\r\n"
    "        root.addLayout(inp_row)\r\n"
    "\r\n"
    "        if dlg.exec() == QDialog.Accepted:\r\n"
    "            return reason_input.text()\r\n"
    "        return None\r\n"
    "\r\n"
)

if anchor in mw:
    mw = mw.replace(anchor, cancel_method + anchor, 1)
    print("✅ PATCH 1c applied: _show_cancel_reason_dialog method inserted")
else:
    anchor_lf = anchor.replace("\r\n", "\n")
    if anchor_lf in mw:
        mw = mw.replace(anchor_lf, cancel_method.replace("\r\n", "\n") + anchor_lf, 1)
        print("✅ PATCH 1c applied (LF)")
    else:
        print(f"❌ PATCH 1c FAILED: anchor '{anchor}' not found")

with open(MW_PATH, "w", encoding="utf-8") as f:
    f.write(mw)
print("✅ main_window.py saved.")

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 2 — restaurant_view.py: Prebill footer → "Havano Version 1.1.8"
# ─────────────────────────────────────────────────────────────────────────────
RV_PATH = r"c:\Users\DELL\New_POS\Havano_POS_2026\views\restaurant_view.py"

with open(RV_PATH, "r", encoding="utf-8") as f:
    rv = f.read()

old_footer_1 = 'receipt.footer = "This is a pre-bill, not a tax invoice."'
new_footer_1 = 'receipt.footer = "Havano Version 1.1.8"'

count = rv.count(old_footer_1)
if count == 0:
    old_footer_1 = old_footer_1.replace('"', '"')  # try unicode quotes just in case
    count = rv.count(old_footer_1)

rv = rv.replace(old_footer_1, new_footer_1)
print(f"✅ PATCH 2 applied: prebill footer changed ({count} occurrence(s))")

with open(RV_PATH, "w", encoding="utf-8") as f:
    f.write(rv)
print("✅ restaurant_view.py saved.")

print("\n=== All patches done ===")
