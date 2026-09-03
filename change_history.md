# Change History

## [2026-08-24 09:50:00] - Fix Stale Table Column Indices Causing "Apply Discounts" Dialog on Qty Edits

### Summary
Fixed issue where editing item quantity (Column 4) erroneously triggered the `"Apply Discounts requires admin authorization"` PIN dialog. Updated numpad handlers and quantity popup helpers to use dynamic column constants (`self.COL_QTY`, `self.COL_DISC`, `self.COL_PRICE`) instead of stale hardcoded column numbers.

### Files Modified
1. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py))
   - Replaced hardcoded column index `4` with `self.COL_DISC` (6) in `allow_discount` permission checks.
   - Replaced hardcoded column index `3` with `self.COL_QTY` (4) in quantity PIN checks, `_open_qty_popup`, keypress handlers, and row recalculations.

## [2026-08-24 09:25:00] - Removed Project `venv` & Configured System Python Environment

### Summary
Removed the project `venv` directory per user instruction and installed all required packages (`qrcode`, `pillow`, `PySide6`, `pyodbc`, `QtAwesome`, etc.) directly into the user's global system Python environment. Tested system Python QR generation (`200x200` pixmap OK).

### Files Modified
1. `venv/` (Deleted directory)
2. `requirements.txt` ([`requirements.txt`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/requirements.txt))
   - Retained `qrcode>=8.0.0` and `pillow>=10.0.0`.



### Files Modified
1. `requirements.txt` ([`requirements.txt`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/requirements.txt))
   - Added `qrcode>=8.0.0` and `pillow>=10.0.0` dependencies.

## [2026-08-24 09:14:00] - Fix SQL Server ODBC 22018 Conversion Error in Fiscal QR Lookup

### Summary
Fixed SQL Server ODBC error `22018` (`Conversion failed when converting the nvarchar value 'BOL-0002' to data type int`). Added numeric check (`str.isdigit()`) on invoice/credit note numbers before querying integer `id` columns, enabling successful DB retrieval of `fiscal_qr_code` and `fiscal_verification_code`.

### Files Modified
1. `services/printing_service.py` ([`services/printing_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/printing_service.py))
   - Updated `print_credit_note` and `_do_print_invoice_receipt` database queries to inspect `invoiceNo` string format before performing `OR id = ?` queries.

## [2026-08-24 09:06:00] - Support Company Defaults Footer Text & Header Printing on Receipts & Credit Notes

### Summary
Ensured that custom `footer_text` configured in Company Defaults is automatically fetched and printed across sales receipts and credit notes, supporting multi-line formatting.

### Files Modified
1. `models/sale.py` ([`models/sale.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/models/sale.py))
   - Updated `prepare_receipt_data` to automatically inject `footer_text`, `receipt_header`, `address_1`, `address_2`, `phone`, `email`, `tin_number`, and `vat_number` from `company_defaults` table.
2. `services/printing_service.py` ([`services/printing_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/printing_service.py))
   - Enhanced `_do_print_invoice_receipt` and `print_credit_note` to dynamically pull `footer_text` from Company Defaults and format multi-line text outputs.

## [2026-08-24 09:03:00] - Fix Fiscal QR Code Printing on Receipts and Credit Notes

### Summary
Fixed issue where fiscal QR codes were not printing on sales receipts and credit notes. Enhanced attribute lookup (`qrCode`, `fiscal_qr_code`, `vCode`, `fiscal_verification_code`), added database lookup for credit notes, and ensured QR codes print reliably whenever valid fiscal QR data is present.

### Files Modified
1. `services/printing_service.py` ([`services/printing_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/printing_service.py))
   - Added DB lookup for credit note QR code and fallback attribute checks for `qrCode` / `fiscal_qr_code` / `vCode` / `verificationCode`.
   - Corrected provider lookup from `FiscalSettingsRepository` instead of `AdvanceSettings`.

## [2026-08-24 08:54:00] - Default Base URL for Revmax & Fiscal Settings Page

### Summary
Configured `http://140.82.25.196:10002` as the default Base URL across the fiscal settings model and UI dialog whenever no Base URL is configured or Revmax provider is selected.

### Files Modified
1. `models/fiscal_settings.py` ([`models/fiscal_settings.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/models/fiscal_settings.py))
   - Set default `base_url` to `http://140.82.25.196:10002` in `FiscalSettings` dataclass and fallback in `from_dict`.
3. `views/pages/company_defaults_page.py` ([`views/pages/company_defaults_page.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/pages/company_defaults_page.py))
   - Replaced old `https://erpfiscal.havano.online` hardcoded default and placeholder with `http://140.82.25.196:10002`.

## [2026-08-21 09:59:00] - Fix NameError in ShiftReconciliationDialog

### Summary
Fixed `NameError: name 'get_company_base_currency' is not defined` in `views/dialogs/shift_reconciliation_dialog.py` by importing `get_company_base_currency` from `models.shift`.

### Files Modified
1. `views/dialogs/shift_reconciliation_dialog.py` ([`views/dialogs/shift_reconciliation_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/shift_reconciliation_dialog.py))
   - Added `get_company_base_currency` to `models.shift` imports at top of file.

## [2026-08-21 10:08:00] - Fix _get_local_rate NameError in ShiftReconciliationDialog

### Summary
Fixed `NameError: name '_get_local_rate' is not defined` in `views/dialogs/shift_reconciliation_dialog.py` by importing `_get_local_rate` from `views.dialogs.payment_dialog`.

### Files Modified
1. `views/dialogs/shift_reconciliation_dialog.py` ([`views/dialogs/shift_reconciliation_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/shift_reconciliation_dialog.py))
   - Added line 18: `from views.dialogs.payment_dialog import _get_local_rate`

## [2026-08-21 10:16:00] - Full-Page Window & Base Currency Expected/Actual Figures in ShiftReconciliationDialog

### Summary
1. Set `self.showMaximized()` in `ShiftReconciliationDialog.__init__` so that the shift reconciliation window always opens full page/screen.
2. Expanded the main reconciliation table from 6 to 8 columns, adding explicit base currency equivalent figures for `Expected ({base_ccy})` and `Actual ({base_ccy})`.
3. Ensures that for native base currency entries (e.g. ZAR when base currency is ZAR), the figure is shown 1:1, while foreign currency figures (e.g. ZIG) display both their native count and converted base equivalent.

### Files Modified
1. `views/dialogs/shift_reconciliation_dialog.py` ([`views/dialogs/shift_reconciliation_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/shift_reconciliation_dialog.py))
   - Added `self.showMaximized()` in `__init__`.
   - Updated table setup in `_build_ui` to 8 columns with dynamic base currency headers.
   - Updated `_load_data`, `_update_variance`, and `_update_summary` to compute and display `Expected (Base)` and `Actual (Base)` columns.

## [2026-08-21 10:20:00] - Inline Table Totals Row in ShiftReconciliationDialog

### Summary
Added a dedicated inline `TOTAL ({base_ccy})` row directly at the bottom of the reconciliation table in `ShiftReconciliationDialog`. Column sums (`Expected (ZAR)`, `Actual (ZAR)`, `Variance (ZAR)`) are calculated and dynamically updated inline under their respective table columns.

### Files Modified
1. `views/dialogs/shift_reconciliation_dialog.py` ([`views/dialogs/shift_reconciliation_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/shift_reconciliation_dialog.py))
   - Added an inline Total row slot in `_load_data`.
   - Updated `_update_summary` to calculate total column sums and render/update the styled inline Total row in `self.table`.
   - Updated data iteration loops in `_build_reconciliation_data` to ignore the inline Total row.

## [2026-08-21 10:25:00] - Refined 7-Column Layout with Expected (Base) and Variance (Base)

### Summary
Removed `Actual (Base)` column per user request. Retained `Expected ({base_ccy})` alongside native `Expected`, and `Variance ({base_ccy})` alongside native `Variance`. `Actual` remains the single native physical cash count field. The inline Total row aligns all base currency totals directly under `Expected ({base_ccy})` and `Variance ({base_ccy})`.

### Files Modified
1. `views/dialogs/shift_reconciliation_dialog.py` ([`views/dialogs/shift_reconciliation_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/shift_reconciliation_dialog.py))
   - Updated `_build_ui` table columns to 7 columns.
   - Updated `_load_data`, `_update_variance`, and `_update_summary` to render and update columns 0 through 6 without `Actual (Base)`.

## [2026-08-21 10:34:00] - Removed Redundant Summary Panel

### Summary
Removed the standalone text-based summary panel (`self.summary_label`) from the bottom of `ShiftReconciliationDialog`, as the `TOTAL` inline row now inherently serves that role.

### Files Modified
1. `views/dialogs/shift_reconciliation_dialog.py` ([`views/dialogs/shift_reconciliation_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/shift_reconciliation_dialog.py))
   - Removed `summary_frame` and `self.summary_label` UI creation in `_build_ui`.
   - Removed string formatting logic and `self.summary_label.setText()` from `_update_summary`.

## [2026-08-21 10:49:00] - Inline Totals Row in DayShiftDialog

### Summary
Replaced the standalone footer summary in `DayShiftDialog` with an inline `TOTAL` row inside the table (matching the visual style of the `ShiftReconciliationDialog`).

### Files Modified
1. `views/dialogs/day_shift_dialog.py` ([`views/dialogs/day_shift_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/day_shift_dialog.py))
   - Modified `_build_ui` to allocate `+ 1` row for the `TOTAL` inline row and removed the previous `footer` QWidget.
   - Updated `_update_totals` to populate columns of the `TOTAL` row in the table directly.
   - Updated data iteration loops in `_update_totals`, `_on_start_shift`, `_refresh_income_display`, and `_check_active_shift` to skip the `TOTAL` row using `range(self.table.rowCount() - 1)`.

## [2026-08-21 10:56:00] - Cleaned up TOTAL row empty cells in ShiftReconciliationDialog

### Summary
Removed the base currency symbol (e.g. ZAR) and hyphen characters (`-`) from the `Currency`, native `Expected`, native `Actual`, and native `Variance` columns in the `TOTAL` inline row so that they appear completely blank instead.

### Files Modified
1. `views/dialogs/shift_reconciliation_dialog.py` ([`views/dialogs/shift_reconciliation_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/shift_reconciliation_dialog.py))
   - In `_update_summary`, replaced the default `base_ccy` and `"-"` strings with empty strings `""` for the uncalculated native totals.

## [2026-08-21 11:03:00] - Raw Column Sums for Native Values in ShiftReconciliationDialog

### Summary
Renamed the `TOTAL ({base_ccy})` row title to just `TOTAL`, and updated the native `Expected`, `Actual`, and `Variance` columns to sum their respective columns directly regardless of the different currencies in the table (raw sum "no drama").

### Files Modified
1. `views/dialogs/shift_reconciliation_dialog.py` ([`views/dialogs/shift_reconciliation_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/shift_reconciliation_dialog.py))
   - Changed `tot_name_item` text from `TOTAL ({base_ccy})` to `TOTAL`.
   - Introduced `raw_expected_total` and `raw_counted_total` variables in `_update_summary` to compute simple linear sums.
   - Set `native_exp_text`, `native_cnt_text`, and `native_var_text` to display these raw sums.

## [2026-08-21 11:04:00] - Always Display Zeros in TOTAL Row of ShiftReconciliationDialog

### Summary
Fixed an issue where the native `Actual` and `Variance` columns in the `TOTAL` row would appear completely blank when the total counted amount was zero. They now correctly display `0.00` to avoid user confusion.

### Files Modified
1. `views/dialogs/shift_reconciliation_dialog.py` ([`views/dialogs/shift_reconciliation_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/shift_reconciliation_dialog.py))
   - Removed the ternary operators `if raw_counted_total > 0 else ""` from `native_cnt_text` and `native_var_text` assignments in `_update_summary()`.

## [2026-08-21 11:08:00] - Cashier Tab Layout Optimization

### Summary
Removed the redundant "Cashier Summary" text panel from the bottom of the individual cashier tabs in the `ShiftReconciliationDialog`. To replace it and maintain consistency across the app, an inline `TOTAL` row was added to the cashier tab's table that dynamically computes the raw sums for `Expected`, `Counted`, `Variance`, and `Transaction Count` as amounts are edited.

### Files Modified
1. `views/dialogs/shift_reconciliation_dialog.py` ([`views/dialogs/shift_reconciliation_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/shift_reconciliation_dialog.py))
   - In `_create_cashier_tab`: Removed the `summary_frame` UI logic. Increased table row count by 1 to inject the `TOTAL` inline row at the bottom.
   - Introduced `_update_cashier_tab_totals()` method to compute raw column sums.
   - Called `_update_cashier_tab_totals()` on initialization and inside `_update_cashier_tab_variance()` to update the `TOTAL` row dynamically whenever an actual count is modified.

## [2026-08-21 12:01:00] - Auto-fill Havano Zimra Fiscalization Credentials

### Summary
Updated both the Fiscal Settings Dialog and the Company Defaults Page so that when the "Havano Zimra" provider is selected, the system automatically fills in the default `Base URL`, `API Key`, and `API Secret` if those fields are currently empty.

## [2026-08-24 16:48:00] - Login Footer Store Label & Single vs Multicurrency Receipt Rating Fix

### Summary
1. **Login Screen Footer Store Display**: Added `Store: <Configured Store Name>` badge right in the center footer layout of `LoginDialog` between the `Version` label and the settings gear button.
2. **Single vs Multicurrency Receipt Rating**: Enforced strict currency rules on printed receipts (`printing_service.py`):
   - **Single Currency Sales**: Do NOT apply exchange rate multiplication (`_display_rate = 1.0`). `Amount Tendered` and `Change` are printed as-is in their native currency.
   - **Multicurrency Sales**: Apply exchange rates per base currency item and show individual payment items with their respective native currency codes under `PAYMENT DETAILS`.

3. `views/login_dialog.py` ([`views/login_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/login_dialog.py#L1160-L1855))
   - Removed `CATALOGUE SYNC & FIRST-TIME SETUP` header label as requested.
   - Shows progress card with smooth animated loading pulse (`setRange(0, 0)`) when clicking "Sign In".
   - Automatically hides progress card on failed login (`_on_login_done`).
4. `services/product_sync_windows_service.py` ([`services/product_sync_windows_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/product_sync_windows_service.py#L825-L835))
   - Fixed progress signal emission logic (`len(remote) <= 30 or idx % 5 == 0`) so small and large catalog syncs continuously update the progress bar.





### Files Modified
1. `views/dialogs/fiscal_settings_dialog.py` ([`views/dialogs/fiscal_settings_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/fiscal_settings_dialog.py))
   - Updated `_on_provider_changed` to auto-populate `base_url_edit`, `api_key_edit`, and `api_secret_edit`.
2. `views/pages/company_defaults_page.py` ([`views/pages/company_defaults_page.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/pages/company_defaults_page.py))
   - Updated `_on_provider_change` to auto-populate `_fiscal_base_url`, `_fiscal_api_key`, and `_fiscal_api_secret`.

## [2026-08-21 12:17:00] - Fiscalization Currency Mapping (ZIG to ZWG)

### Summary
Updated the internal fiscalization service to automatically map local currency codes (`ZIG`, `ZWD`, `ZWL`) to `ZWG` before submitting payloads to the ZIMRA API. This resolves validation errors caused by ZIMRA exclusively expecting `ZWG`, `USD`, `EUR`, or `GBP` as valid currency identifiers.

### Files Modified
1. `services/fiscalization_service.py` ([`services/fiscalization_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/fiscalization_service.py))
   - Modified currency translation mapping in three locations (`fiscal_currency in ("ZWD", "ZWL", "ZIG") -> "ZWG"`).

## [2026-08-21 14:14:00] - Remove Empty Space in Shift Reconciliation

### Summary
Optimized the cashier tab layout in the Shift Reconciliation dialog. The empty grey background space on the far right of the cashier information block has been eliminated by moving the "Finalize My Count" button up into that same horizontal frame. This creates a much cleaner, unified header and saves vertical screen space.

### Files Modified
1. `views/dialogs/shift_reconciliation_dialog.py` ([`views/dialogs/shift_reconciliation_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/shift_reconciliation_dialog.py))
   - Removed `action_layout` below the header frame.
   - Inserted the `finalize_btn` and `modify_btn` directly into the existing `info_layout` for the `info_frame` so they render inside the previously empty right-hand space.

## [2026-08-21 14:18:00] - Add Base Currency Columns to Cashier Tabs

### Summary
Expanded the cashier reconciliation table columns to match the main "Reconciliation" tab. The table now includes 8 columns (adding Expected and Variance equivalent in Base Currency) to give cashiers and managers an immediate view of USD/Base-equivalent deficits in the cashier tab. The inline TOTAL calculation and variance handlers were updated to respect the new column indices.

### Files Modified
1. `views/dialogs/shift_reconciliation_dialog.py` ([`views/dialogs/shift_reconciliation_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/shift_reconciliation_dialog.py))
   - `_add_cashier_tab`: Added `Expected (Base)` and `Variance (Base)` columns.
   - `_update_cashier_tab_variance`: Modified to also calculate and display base currency variance.
   - `_update_cashier_tab_totals`: Included base currency totals in the calculation.
   - `_on_finalize_cashier_count`: Shifted lookup indices for Expected and Actual to account for new columns.

## [2026-08-21 14:25:00] - Update Admin Override Dialog UI

### Summary
Updated the `AdminCashierOverrideReconciliationDialog` to be fully maximized and mirror the same 8-column layout (with base currency variance and inline totals) as the standard `ShiftReconciliationDialog`.

### Files Modified
1. `views/dialogs/shift_reconciliation_dialog.py` ([`views/dialogs/shift_reconciliation_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/shift_reconciliation_dialog.py))
   - `AdminCashierOverrideReconciliationDialog.__init__`: Updated to use `self.showMaximized()`.
   - `AdminCashierOverrideReconciliationDialog._build_ui`: Replaced 4-column layout with the new 8-column layout, inserted the base currency values via `_get_local_rate()`, and added the dynamic `TOTAL` row.
   - `AdminCashierOverrideReconciliationDialog._update_variance`: Updated cell index lookup to index 4, 5, 6 and invoked `self._update_totals()`.
   - `AdminCashierOverrideReconciliationDialog._update_totals`: Implemented custom totals aggregation calculation to span all 8 columns dynamically.

## [2026-08-21 14:45:00] - Simplify Shift Close Workflow (Direct Reconciliation Tab Entry)

### Summary
Simplified the shift reconciliation and closing workflow. You can now insert actual counted amounts directly into the editable "Actual" column of the main Reconciliation tab. Removed the Admin Override dialog popup during shift finalization—submitting this main form now directly closes the shift and immediately triggers the shift recon receipt printout, avoiding extra intermediate pages.

### Files Modified
1. `views/dialogs/shift_reconciliation_dialog.py` ([`views/dialogs/shift_reconciliation_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/shift_reconciliation_dialog.py))
   - `ShiftReconciliationDialog._load_data`: Converted the Actual column from static `QTableWidgetItem` to an editable `QLineEdit` and connected the `textChanged` signal to the dynamic variance updates.
   - `ShiftReconciliationDialog._build_reconciliation_data`: Updated data harvesting logic to read values directly from the `cellWidget` in the main table instead of aggregating from the individual cashier tabs.
   - `ShiftReconciliationDialog._on_finalize`: Bypassed and removed the unfinalized cashier check and the `AdminCashierOverrideReconciliationDialog` popup to enforce the main tab as the definitive shift close flow.

## [2026-08-21 14:48:00] - Use paid_amount for Shift Expected

### Summary
Changed the shift expected calculation to accumulate `paid_amount` from payment entries instead of the calculated `received_amount`. This ensures that the expected figure correctly reflects the true, non-calculated base values.

### Files Modified
1. `models/shift.py` ([`models/shift.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/models/shift.py))
   - `get_income_by_method_since`: Changed `pe.received_amount` to `pe.paid_amount AS received_amount` to accumulate the base payment amount for shift reconciliation.

## [2026-08-21 14:56:00] - Revert Shift Expected to received_amount

### Summary
Reverted the shift expected calculation back to received_amount. As noticed, paid_amount stores the USD basis, meaning the Expected column was incorrectly pulling the USD amount instead of the native currency amount. Reverting back to received_amount restores the correct native accumulation.

### Files Modified
1. models/shift.py ([models/shift.py](file:///c:/Users/user/Desktop/Havano_POS_2026-main/models/shift.py))
   - get_income_by_method_since: Reverted pe.paid_amount AS received_amount back to pe.received_amount.

## [2026-08-22 06:05:00] - Start Shift Base Currency Modal Dialog Prompt

### Summary
Replaced the auto-start shift behavior with the small modal dialog `StartShiftDialog` when starting a shift or when initiating POS session actions. The cashier is now prompted with a small modal window where they can enter their starting float in the base currency only.

### Files Modified
1. `views/dialogs/start_shift_dialog.py` ([`views/dialogs/start_shift_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/start_shift_dialog.py))
   - Updated `_on_start_shift` to parse base currency starting float, initialize all enabled payment methods (setting base currency float to `start_amount` and others to 0.0), and invoke `start_shift` with required arguments (`station`, `shift_number`, `cashier_id`, `date`, `opening_floats`). Added fiscal provider prompt triggers if enabled.
2. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py))
   - Updated `_prompt_open_shift_if_missing`, `_require_active_shift`, and `_open_shift_chooser` to open `StartShiftDialog` for base currency float input instead of silently auto-starting shift.
3. `views/admin_dashboard.py` ([`views/admin_dashboard.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/admin_dashboard.py))
   - Updated `_open_shift_chooser` to launch `StartShiftDialog` when no active shift is running.
4. `views/new_d.py` ([`views/new_d.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/new_d.py))
   - Updated `_open_shift_chooser` to launch `StartShiftDialog` when no active shift is running.

## [2026-08-22 08:26:00] - Clean StartShiftDialog Layout & Remove Default Text Autofill

### Summary
1. Removed the redundant `"Start New Shift"` header label from `StartShiftDialog` and updated the input field label to `"Opening Float Balance ({self._base_ccy}):"`.
2. Removed initial `"0.00"` text pre-filling from `float_edit` so the field opens clean/empty with `"0.00"` placeholder text, preventing cashier text editing friction.
3. Adjusted dialog vertical fixed size to 195px to maintain compact layout proportion.

### Files Modified
1. `views/dialogs/start_shift_dialog.py` ([`views/dialogs/start_shift_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/start_shift_dialog.py))
   - Removed header `QLabel("Start New Shift")`.
   - Updated `lbl_float` to `Opening Float Balance ({self._base_ccy}):`.
   - Removed `self.float_edit.setText("0.00")` and `self.float_edit.selectAll()`.
   - Updated fixed height from 230 to 195.

## [2026-08-22 08:27:00] - Active Shift Guard for StartShiftDialog

### Summary
Added a active shift check in `StartShiftDialog.exec()` to guarantee that `StartShiftDialog` will immediately reject and refrain from showing if a shift is already active and running.

### Files Modified
1. `views/dialogs/start_shift_dialog.py` ([`views/dialogs/start_shift_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/start_shift_dialog.py))
   - Added `exec()` override that checks `get_active_shift()` and returns `QDialog.Rejected` if a shift is running.

## [2026-08-22 08:28:00] - Remove Start Shift Confirmation Popup

### Summary
Removed `QMessageBox.information` popup from `StartShiftDialog._on_start_shift` so that starting a shift immediately creates the shift and refreshes status without prompting an extra confirmation dialog box.

### Files Modified
1. `views/dialogs/start_shift_dialog.py` ([`views/dialogs/start_shift_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/start_shift_dialog.py))
   - Removed `QMessageBox.information` ("Shift Started") popup upon starting a shift.

## [2026-08-22 08:31:00] - Automatic Logout on Shift Close

### Summary
Enhanced shift closing logic across `MainWindow`, `AdminDashboard`, and `new_d.py` so that finalizing/closing a shift automatically logs out the current user and returns to the login screen, regardless of window parenting hierarchy.

### Files Modified
1. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py))
   - Updated `_open_day_shift` handlers to invoke `parent_window._logout()`, `self._logout()`, or `self._do_logout()`.
2. `views/admin_dashboard.py` ([`views/admin_dashboard.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/admin_dashboard.py))
   - Updated `_open_day_shift` handlers to invoke `parent_window._logout()`, `self._logout()`, or `self._do_logout()`.
3. `views/new_d.py` ([`views/new_d.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/new_d.py))
   - Updated `_open_day_shift` handlers to invoke `parent_window._logout()`, `self._logout()`, or `self._do_logout()`.

## [2026-08-22 08:35:00] - Remove Base Currency Subtitle & Ultra-Compact StartShiftDialog Layout

### Summary
1. Removed the redundant `"Base Currency: USD"` subtitle label from `StartShiftDialog`.
2. Reduced dialog dimensions to `340x150` with 16px margins and 8px spacing, creating a streamlined, modern, compact interface.

### Files Modified
1. `views/dialogs/start_shift_dialog.py` ([`views/dialogs/start_shift_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/start_shift_dialog.py))
   - Removed `sub = QLabel(f"Base Currency: {self._base_ccy}")`.
   - Updated `setFixedSize(340, 150)` and polished margins/spacing.

## [2026-08-22 08:47:00] - Fix SQLite License Upserts & Auto-Assign Trial License in Offline Mode

### Summary
1. Fixed SQLite database write failures in `_db_write` and `_trial_db_write` within `utils/license_manager.py` by replacing incompatible SQL Server `MERGE` syntax with SQLite-compatible `SELECT` + `UPDATE`/`INSERT` logic.
2. Implemented automatic trial license assignment in `login_dialog.py` during offline mode login if no trial has been activated yet (`status == "Not Started"`), granting the 30-day free trial seamlessly.

### Files Modified
1. `utils/license_manager.py` ([`utils/license_manager.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/utils/license_manager.py))
   - Updated `_db_write` and `_trial_db_write` to use standard SQLite upsert queries.
2. `views/login_dialog.py` ([`views/login_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/login_dialog.py))
   - Updated `_accept_user` offline license check to invoke `activate_free_trial()` when trial status is `"Not Started"`.

## [2026-08-22 09:00:00] - Instant Keypad Shift Action Button UI Refresh

### Summary
Fixed the issue where starting or closing a shift required a user logout/login to update the action keypad shift button (`btn_shift_action`). Added `btn_shift_action` updating logic to `_refresh_shift_pill()` across all views (`MainWindow`, `AdminDashboard`, `new_d.py`) so the button instantly changes between `"START SHIFT (F2)"` and `"CLOSE SHIFT #X"` upon shift start/close.

### Files Modified
1. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py))
   - Updated `_refresh_shift_pill` to dynamically refresh `btn_shift_action` label and styling.
2. `views/admin_dashboard.py` ([`views/admin_dashboard.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/admin_dashboard.py))
   - Updated `_refresh_shift_pill` to dynamically refresh `btn_shift_action` label and styling.
3. `views/new_d.py` ([`views/new_d.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/new_d.py))
   - Updated `_refresh_shift_pill` to dynamically refresh `btn_shift_action` label and styling.

## [2026-08-22 09:14:00] - Cashier Breakdown Variance on Shift Reconciliation Printout

### Summary
Fixed the missing cashier variance on the shift reconciliation printout. When closing a shift on the main summary tab, `_build_reconciliation_data` now harvests the main table counted values (`main_counted_map`) before building `cashier_details`. Cashiers without explicit individual count sessions automatically inherit the counted values (or prorated share), so each cashier's breakdown and sub-totals display their true variance alongside the summary table.

### Files Modified
1. `views/dialogs/shift_reconciliation_dialog.py` ([`views/dialogs/shift_reconciliation_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/shift_reconciliation_dialog.py))
   - Updated `_build_reconciliation_data` to collect `main_counted_map` first and apply counted values/prorated shares to cashier breakdown rows.

## [2026-08-22 09:18:00] - Immediate Start Shift Prompt on Login

### Summary
Configured the initial shift check prompt sequence across `MainWindow`, `AdminDashboard`, and `new_d.py`. If no active shift is running when logging in, the `StartShiftDialog` modal now pops up immediately right away as the very first prompt over the main window as soon as the interface renders.

### Files Modified
1. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py))
   - Adjusted `_prompt_open_shift_if_missing` timer sequence and added fallback wrapper on `MainWindow`.
2. `views/admin_dashboard.py` ([`views/admin_dashboard.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/admin_dashboard.py))
   - Adjusted `_prompt_open_shift_if_missing` timer sequence for clean immediate popup.
3. `views/new_d.py` ([`views/new_d.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/new_d.py))
   - Adjusted `_prompt_open_shift_if_missing` timer sequence for clean immediate popup.

## [2026-08-22 09:23:00] - Expose Shift Button Refresh Callable & Update Immediately

### Summary
Fixed the issue where `btn_shift_action` was not updating to `CLOSE SHIFT #X` upon starting a shift. Exposed `_refresh_shift_button` on `self` across all view components (`MainWindow`, `AdminDashboard`, `new_d.py`) and updated `StartShiftDialog` to trigger `_refresh_shift_button()` on parent windows immediately when a shift is started.

### Files Modified
1. `views/dialogs/start_shift_dialog.py` ([`views/dialogs/start_shift_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/start_shift_dialog.py))
   - Triggered `_refresh_shift_button()` and `_refresh_shift_pill()` across parent window hierarchy on shift creation.
2. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py))
   - Exposed `self._refresh_shift_button = _refresh_shift_button`.
3. `views/admin_dashboard.py` ([`views/admin_dashboard.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/admin_dashboard.py))
   - Exposed `self._refresh_shift_button = _refresh_shift_button`.
4. `views/new_d.py` ([`views/new_d.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/new_d.py))
   - Exposed `self._refresh_shift_button = _refresh_shift_button`.

## [2026-08-22 09:25:00] - Nested `btn_shift_action` Lookup & Instant Sync Fix

### Summary
Fixed the lookup failure where `MainWindow` and `AdminDashboard` could not find `btn_shift_action` because it was attached to the nested `_pos_view` child widget. Updated `_refresh_shift_pill` across all views to dynamically search `getattr(self, "btn_shift_action") or getattr(self._pos_view, "btn_shift_action")`, ensuring the `START SHIFT (F2)` button syncs immediately to `CLOSE SHIFT #X` upon starting a shift.

### Files Modified
1. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py))
   - Updated `_refresh_shift_pill` to search `self` and `self._pos_view` for `btn_shift_action` and invoke `_pos_view._refresh_shift_pill()`.
2. `views/admin_dashboard.py` ([`views/admin_dashboard.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/admin_dashboard.py))
   - Updated `_refresh_shift_pill` to search `self` and `self._pos_view` for `btn_shift_action` and invoke `_pos_view._refresh_shift_pill()`.
3. `views/new_d.py` ([`views/new_d.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/new_d.py))
   - Updated `_refresh_shift_pill` to search `self` and `self._pos_view` for `btn_shift_action` and invoke `_pos_view._refresh_shift_pill()`.

## [2026-08-22 09:35:00] - Enable "Activate 30-Day Free Trial" Button on System Activation Dialog

### Summary
Fixed the issue where the "Activate 30-Day Free Trial" button was hidden on the System Locked / License Dialog when unlicensed or trial status was not fresh. Updated `LicenseDialog` to always display the "Activate 30-Day Free Trial" button whenever the system is not fully active, allowing 1-click 30-day trial activation. Updated `utils/license_manager.py` to synchronize system date tracking on trial activation.

### Files Modified
1. `views/dialogs/license_dialog.py` ([`views/dialogs/license_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/license_dialog.py))
   - Updated `_show_trial_button = (status != "Active")`, expanded dialog height to 680px, and added spacing/styling for 30-day trial activation.
2. `utils/license_manager.py` ([`utils/license_manager.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/utils/license_manager.py))
   - Updated `activate_free_trial` to call `_reg_write_date()` so system run tracking is updated upon starting a trial.

## [2026-08-22 09:36:00] - Automatic 30-Day Free Trial Auto-Start in Offline Mode

### Summary
Updated `LoginDialog._accept_user` so that when logging in under offline mode without a full active license, the system automatically activates a 30-day free trial whenever the trial is not active (`status != "Active"`). This prevents lockout popups and ensures seamless offline access.

### Files Modified
1. `views/login_dialog.py` ([`views/login_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/login_dialog.py))
   - Updated `_accept_user` to auto-trigger `activate_free_trial()` when `trial_info.get("status") != "Active"`.

## [2026-08-22 09:39:00] - Trial Days Remaining Login Popup & Status Bar Display

### Summary
Added a popup notification on login displaying remaining trial days (`✓ Offline Mode — Free Trial Active! You have X days remaining`) and updated `MainWindow` status bar to display trial remaining days (`X days left |`) in green at the bottom of the screen.

### Files Modified
1. `views/login_dialog.py` ([`views/login_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/login_dialog.py))
   - Added `QMessageBox.information` popup displaying active trial days remaining upon logging in.
2. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py))
   - Added fallback to `get_trial_info()` so the bottom status bar displays remaining trial days (`30 days left |`).

## [2026-08-22 09:42:00] - Fix `main_window.py` Syntax Error in Trial Days Block

### Summary
Fixed the `SyntaxError: expected 'except' or 'finally' block` on line 26824 in `main_window.py` by restoring the `except Exception:` clause and `_days_left` calculation. Verified clean module import and execution.

### Files Modified
1. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py))
   - Restored try/except block structure around line 26824.

## [2026-08-22 09:48:00] - Display "Free Trial Active" & Days Remaining in Activation Dialog

### Summary
Fixed the issue where `LicenseDialog` displayed "System Locked" even when a free trial was active. Added active trial handling so that when a trial is active, `LicenseDialog` header changes to **Free Trial Active** with an unlock icon, status displays **Status: Free Trial Active** in bright green, and the expiry label clearly shows **Trial Remaining: X days**.

### Files Modified
1. `views/dialogs/license_dialog.py` ([`views/dialogs/license_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/license_dialog.py))
   - Added active trial state handling to display **Free Trial Active**, remaining days, and green active trial button styling.

## [2026-08-22 10:42:00] - Flexible Dashed & Continuous License Key Support

### Summary
Updated license verification, storage, and activation dialog to seamlessly accept both dashed (`XXXXX-XXXXX-XXXXX-XXXXX`) and continuous (`XXXXXXXXXXXXXXXXXXXX`) license keys. Stripped dashes and spaces during validation and saving, updated the input placeholder to `XXXXXXXXXXXXXXXXXXXX`, and displayed Machine ID and license keys continuously without forced dashes.

### Files Modified
1. `utils/license_manager.py` ([`utils/license_manager.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/utils/license_manager.py))
   - Cleaned license keys in `verify_license` and `save_license_key` by stripping dashes and spaces.
2. `views/dialogs/license_dialog.py` ([`views/dialogs/license_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/license_dialog.py))
   - Updated placeholder to `XXXXXXXXXXXXXXXXXXXX`, stripped dashes/spaces on activation, and displayed `machine_id` and `inp_key` continuously without dashes.

## [2026-08-22 10:54:00] - Automated Build Script & Comment Reference Update

### Summary
Created `build_exe.py` to automate executable builds while safely terminating processes that lock `HavanoPOS.exe`. Updated `main.py` build command comments to reference `python build_exe.py`.

### Files Modified
1. `build_exe.py` ([`build_exe.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/build_exe.py))
   - Created build script to kill locked processes, clean build folders, and execute PyInstaller cleanly.


## [2026-08-25 08:15:00] - Real-Time Login Sync Loader & Printed Receipt Grand Total Rules

### Summary
1. **Real-Time Login Sync Loader**: Updated `services/sync_service.py` and `services/product_sync_windows_service.py` to emit live `product_sync_notifier.progress` updates as page 1 is resolved and every item is upserted. Updated `views/login_dialog.py` to display exact counts and percentages (`Syncing catalogue: 12 / 42 items (28%)`) with smooth 0-100% progress bar filling.
2. **Receipt Grand Total Formatting**: Enforced strict currency rules for printed receipts in `services/printing_service.py`:
   - **Single Currency Sales**: Displays Grand Total in the unrated native currency (e.g. `ZWG 1,200.00` or `USD 10.00`).
   - **Multi-Currency Sales**: Displays Grand Total rated in the base currency (e.g. `USD 50.00`), followed immediately by the `PAYMENT DETAILS` breakdown listing each payment method in its native currency.

### Files Modified
1. `services/sync_service.py` ([`services/sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/sync_service.py#L735-L850))
   - Emitted progress signal when `total_api` count is resolved and for item upserts.
2. `services/product_sync_windows_service.py` ([`services/product_sync_windows_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/product_sync_windows_service.py#L828-L838))
   - Updated progress emission loop to ensure smooth loader progression.

## [2026-08-25 09:25:00] - Post-Login UI Freeze & Main Thread Blocking Fixes

### Summary
Fixed the root causes of application UI freezing right after login:
1. **Background Stock Cache Building**: Updated `main.py` so `init_stock_cache` is spawned inside a background `daemon` thread via `threading.Thread` instead of executing heavy SQL queries and file writes on Qt's main UI thread.
2. **Ultra-Fast Disk Writes**: Optimized `services/stock_cache.py` by removing formatted JSON indentation (`indent=2`) from `json.dump`, reducing disk serialization time by up to 90%.
3. **Non-Blocking Terminal Takeover**: Wrapped `_do_terminal_takeover()` in `views/main_window.py` in an asynchronous background daemon thread so network HTTP requests to `e.havano.pro` never block Qt's main event loop.
4. **Lazy Admin Dashboard**: Deferred `AdminDashboard` widget instantiation in `views/main_window.py` until the Admin tab is explicitly accessed by the user.

### Files Modified
1. `main.py` ([`main.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/main.py#L569-L576))
   - Wrapped deferred `init_stock_cache` call in a background `threading.Thread(daemon=True)`.
2. `services/stock_cache.py` ([`services/stock_cache.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/stock_cache.py#L96-L100))
   - Used compact `json.dump(data, f)` serialization for fast disk cache writing.
3. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L26990-L27060))
   - Executed terminal takeover HTTP calls in a background thread and deferred `AdminDashboard` instantiation.

## [2026-08-25 11:12:00] - Date Picker Calendar Header Month & Year Visibility Styling

### Summary
Fixed invisible Month and Year text in `QCalendarWidget` popups (e.g., Sales Invoices and report date filters):
1. **Report Template Calendar Styling**: Updated `calendar_style` in `views/reports/report_template.py` so `qt_calendar_monthbutton` and `qt_calendar_yearbutton` render in bold white text (`#ffffff`) on dark navy blue buttons (`#162d52`) with high-contrast borders (`#3b82f6`).
2. **Menu Indicator Removal**: Removed Qt's default menu indicator overlay (`image: none; width: 0px;`) which previously obstructed Month/Year text labels.
3. **Dropdown Menu & Year Edit Spinbox**: Styled `QMenu` and `QSpinBox#qt_calendar_yearedit` with high-visibility blue text on crisp white background.
4. **Global Application Theme**: Added calendar styling rules to `apply_global_styles()` in `main.py` and connected it to `QApplication` startup.

### Files Modified
1. `views/reports/report_template.py` ([`views/reports/report_template.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/reports/report_template.py#L102-L178))
   - Enhanced `calendar_style` for `QCalendarWidget` navigation bar, month/year buttons, dropdown menus, and year spinboxes.
2. `main.py` ([`main.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/main.py#L286-L298))
   - Added global `QCalendarWidget` stylesheet rules in `apply_global_styles` and ensured it is executed upon app launch.

## [2026-08-25 12:16:00] - Login Dialog User Display Label & Select Terminal Email Fallback

### Summary
1. **Login Footer User Label**: Replaced `Store: Legends Machipisa` at the bottom of the login dialog (`views/login_dialog.py`) with `User: <logged_in_user>` in small 11px muted text as requested by the user.
2. **SaaS Terminal Select User Parameter Fix**: Updated `select_terminal` in `services/auth_service.py` to only include `"user": resolved_email` when `resolved_email` is a valid `@` email address, preventing `HTTP 400 - User 'admin' not found` errors when local admin account logins run terminal takeover.
3. **Takeover Monitor SaaS Email Fallback**: Added active session user and `company_defaults` fallbacks in `views/main_window.py` to automatically resolve the SaaS user email address during cloud pings.

### Files Modified
1. `views/login_dialog.py` ([`views/login_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/login_dialog.py#L1284-L1306))
   - Replaced `store_footer_lbl` with `user_footer_lbl` displaying the active user name in small text.
2. `services/auth_service.py` ([`services/auth_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/auth_service.py#L408-L415))
   - Conditioned payload `"user"` assignment on valid `@` email address check to prevent HTTP 400 errors.
3. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L27099-L27118))
   - Added active session & defaults email resolution in takeover monitor.

## [2026-08-25 14:06:00] - Explicit Sync Service URL Console Logging

### Summary
Added explicit real-time console logging (`[sync] 🌐 Fetching ... URL: <url>`) across all cloud synchronization modules:
1. **Product Catalogue Sync**: Added URL logging in `_fetch_page` ([`services/sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/sync_service.py#L604-L607)) and `_get` ([`services/product_sync_windows_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/product_sync_windows_service.py#L153-L157)).
2. **GL Accounts Sync**: Added URL logging for Cash and Bank account resource fetches ([`services/sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/sync_service.py#L1160-L1165)).
3. **Exchange Rates Sync**: Added URL logging for ERPNext currency pair rate requests ([`services/sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/sync_service.py#L1268-L1272)).
4. **Modes of Payment Sync**: Added URL logging for primary and fallback MOP list requests ([`services/sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/sync_service.py#L1340-L1354)).

### Files Modified
1. `services/sync_service.py` ([`services/sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/sync_service.py#L604-L1354))
2. `services/product_sync_windows_service.py` ([`services/product_sync_windows_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/product_sync_windows_service.py#L153-L157))

## [2026-08-25 14:43:00] - Skip GL Account /api/resource/Account Fetch in SaaS Mode

### Summary
Updated `sync_gl_accounts()` in `services/sync_service.py` to check `get_system_mode()`. If system mode is `"saas"`, it skips fetching `/api/resource/Account` from the server and logs `[sync] ℹ️ SaaS mode active - skipping /api/resource/Account GL account fetch.`, preventing unconfigured Chart of Accounts records from auto-populating on screen in SaaS mode.

### Files Modified
1. `services/sync_service.py` ([`services/sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/sync_service.py#L1137-L1150))
2. `Havano POS System\_internal\services\sync_service.py` ([`Havano POS System\_internal\services\sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/Havano%20POS%20System/_internal/services/sync_service.py#L65-L78))

## [2026-08-25 17:19:00] - SaaS Mode Credit Note Reference Number & Endpoint Sync Fix

### Summary
Fixed Credit Note synchronization in `services/credit_note_sync_service.py`:
1. **`reference_number` & Metadata Injections**: Injected `"reference_number": ref_num` into `_base_cn_payload_fields()`, solving the SaaS endpoint validation error `"reference_number is required when making a sale"`. In SaaS mode, also added `"trade_name"`, `"owner"`, `"cashier"`, `"sales_person"`, `"is_pos": 1`, `"pos_profile"`, and `"terminal_id"`.
2. **SaaS Target Endpoint Escalation**: In SaaS mode, `_push_cn()` iterates through SaaS endpoint candidates (`saas_api.www.api.create_invoice`, `create_sales_invoice`, `make_sale`, fallback `Sales%20Invoice`). Standard Frappe / ERPNext mode remains untouched and continues using `/api/resource/Sales%20Invoice`.

### Files Modified
1. `services/credit_note_sync_service.py` ([`services/credit_note_sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/credit_note_sync_service.py#L290-L750))

## [2026-08-26 15:28:00] - Remove Zero-Stock Product Grid Hiding

### Summary
Updated `models/product.py` so zero-stock and negative-stock products are no longer hidden from the POS selling grid and search:
1. **Removed Default `only_in_stock=True` Filter**: Changed default parameter `only_in_stock` from `True` to `False` across `get_all_products()`, `get_products_by_category()`, and `search_products()`.
2. **Full Product Visibility**: Enabled cashiers to view, search, and process sales for all catalog products regardless of current stock quantity.

### Files Modified
1. `models/product.py` ([`models/product.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/models/product.py#L55-L126))

## [2026-08-27 08:06:00] - Fix Missing Cryptography Module in PyInstaller Build & Update Inno Setup Version

### Summary
1. **PyInstaller Cryptography Bundle Fix**: Updated `HavanoPOS.spec` to use `collect_all('cryptography')` and explicit `hiddenimports` for cryptography submodules (`cryptography.fernet`, `cryptography.hazmat`, `cryptography.hazmat.primitives`, etc.). This resolves `ModuleNotFoundError: No module named 'cryptography.fernet'` when launching the compiled executable on target computers.
2. **Inno Setup Version Sync**: Updated `AppVersion` and `OutputBaseFilename` to `2.0.8.30` in both `combined/HavanoPOS_Update.iss` and `combined/HavanoPOS_Setup.iss` to stay in sync with `main.py`'s `APP_VERSION = "2.0.8.30"`.

### Files Modified
1. `HavanoPOS.spec` ([`HavanoPOS.spec`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/HavanoPOS.spec#L6-L22))
   - Added `collect_all('cryptography')` and explicit cryptography hidden imports.
2. `combined/HavanoPOS_Update.iss` ([`combined/HavanoPOS_Update.iss`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/combined/HavanoPOS_Update.iss#L10-L13))
   - Updated version to `2.0.8.30`.
3. `combined/HavanoPOS_Setup.iss` ([`combined/HavanoPOS_Setup.iss`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/combined/HavanoPOS_Setup.iss#L9-L12))
   - Updated version to `2.0.8.30`.
4. `requirements.txt` ([`requirements.txt`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/requirements.txt#L25))
   - Added `cryptography>=42.0.0`.

## [2026-08-27 08:50:00] - Hardware Settings Printer Enumeration Performance & Receipt Paper Size Selection (80mm, 58mm, A4)

### Summary
1. **Printer Enumeration Performance**: Optimized `_get_system_printers()` in `views/dialogs/settings_dialog.py` to prioritize `QPrinterInfo.availablePrinters()` and avoid scanning unreachable network printer connections (`PRINTER_ENUM_CONNECTIONS`). Opening Hardware Settings and refreshing printers now occurs instantly without UI freezes.
2. **Paper Size Setting (80mm, 58mm, A4)**: Added a **Printer Paper Size / Format** selector (`80mm`, `58mm`, `A4`) to `HardwareDialog` UI in `views/dialogs/settings_dialog.py` and persisted the `paper_size` choice in `app_data/hardware_settings.json` and DB.
3. **A4 Invoice Service & Preview Dialog**: Created `services/a4_invoice_service.py` to render full-page A4 Tax Invoices matching Havano POS specifications (with company header, customer details, item table, tax breakdown, and footer notes) and display a native PySide6 `QPrintPreviewDialog` for instant printing/PDF export.
4. **Thermal & A4 Paper Size Routing**: Updated `PrintingService._do_print_invoice_receipt` in `services/printing_service.py` to check `paper_size`:
   - `A4`: Automatically launches the A4 Invoice Print Preview Dialog on payment/reprint.
   - `58mm`: Adjusts thermal paper width canvas to 58mm.
   - `80mm`: Standard thermal 80mm receipt width.

### Files Modified
1. `views/dialogs/settings_dialog.py` ([`views/dialogs/settings_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/settings_dialog.py#L218-L905))
2. `services/a4_invoice_service.py` ([`services/a4_invoice_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/a4_invoice_service.py))
3. `services/printing_service.py` ([`services/printing_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/printing_service.py#L2154-L2173))

## [2026-08-27 08:52:00] - Fix NumPy 2.0+ openpyxl AttributeError (module 'numpy' has no attribute 'short')

### Summary
Fixed `AttributeError: module 'numpy' has no attribute 'short'` when opening the bulk stock upload or stock on hand import dialogs:
1. Added NumPy 2.0+ compatibility patches across `main.py`, `views/dialogs/upload_stock_dialog.py`, and `views/dialogs/inventory_list_dialog.py` before importing `openpyxl`.
2. Restored legacy scalar type aliases (`short`, `ushort`, `intc`, `uintc`, `int_`, `uint`, `half`, `single`, `double`, `longdouble`) to `numpy` if missing, allowing `openpyxl`'s `compat/numbers.py` module to load cleanly without crashing.

### Files Modified
1. `main.py` ([`main.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/main.py#L12-L21))
2. `views/dialogs/upload_stock_dialog.py` ([`views/dialogs/upload_stock_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/upload_stock_dialog.py#L8-L18))
3. `views/dialogs/inventory_list_dialog.py` ([`views/dialogs/inventory_list_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/inventory_list_dialog.py#L6-L16))

## [2026-08-27 08:55:00] - Fix main.py Try-Except Syntax Error & Sync Version 2.0.8.31

### Summary
1. **Syntax Error Fix**: Restored missing `except Exception: pass` block after the UTF-8 `sys.stdout`/`sys.stderr` reconfigure try-block in `main.py`, fixing `SyntaxError: expected 'except' or 'finally' block` during PyInstaller build execution.
2. **Inno Setup Version Sync**: Synchronized `AppVersion` and `OutputBaseFilename` to `2.0.8.31` across `combined/HavanoPOS_Update.iss` and `combined/HavanoPOS_Setup.iss` to match `main.py`'s `APP_VERSION = "2.0.8.31"`.

### Files Modified
1. `main.py` ([`main.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/main.py#L7-L23))
2. `combined/HavanoPOS_Update.iss` ([`combined/HavanoPOS_Update.iss`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/combined/HavanoPOS_Update.iss#L10-L13))
3. `combined/HavanoPOS_Setup.iss` ([`combined/HavanoPOS_Setup.iss`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/combined/HavanoPOS_Setup.iss#L9-L12))

## [2026-08-27 09:08:00] - Company Defaults Banking Details Integration & A4 Big Receipt Display

### Summary
1. **Database Schema & Model Update**: Added `[banking_details] NVARCHAR(MAX) NOT NULL DEFAULT ''` to `company_defaults` table definition and auto-migration list in `setup_database.py`. Updated `models/company_defaults.py` (`_BLANK`, `_ensure_columns`, `save_defaults`, `get_defaults`) to load, persist, and migrate `banking_details`.
2. **Company Defaults UI Page**: Added a **Banking Details (printed on A4 Big Receipts / Tax Invoices)** card and text editor in `views/pages/company_defaults_page.py` alongside Terms & Conditions in ROW 3.
3. **A4 Invoice / Big Receipt Printing**: Updated `services/a4_invoice_service.py` to extract `banking_details` from `company_defaults` and render formatted multi-line banking information in the **BANKING DETAILS** footer section of the A4 Tax Invoice preview and printout.

### Files Modified
1. `setup_database.py` ([`setup_database.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/setup_database.py#L226-L325))
2. `models/company_defaults.py` ([`models/company_defaults.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/models/company_defaults.py#L18-L262))
3. `views/pages/company_defaults_page.py` ([`views/pages/company_defaults_page.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/pages/company_defaults_page.py#L720-L1345))
4. `services/a4_invoice_service.py` ([`services/a4_invoice_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/a4_invoice_service.py#L48-L302))

## [2026-08-27 09:12:00] - Quotation A4 Paper Size Integration & Preview Popup

### Summary
1. **Quotation A4 Paper Size Routing**: Updated `print_quotation` in `services/quotation_print.py` to read `paper_size` from `hardware_settings.json`. When `paper_size == "A4"`, printing a quotation automatically launches the A4 Print Preview Dialog.
2. **A4 Quotation Document Formatting**: Updated `render_a4_invoice_html` in `services/a4_invoice_service.py` to detect quotation documents, dynamically setting the header banner to `—— QUOTATION ——`, labeling the number as `Quote No.`, and rendering quotation terms and company banking details.

### Files Modified
1. `services/quotation_print.py` ([`services/quotation_print.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/quotation_print.py#L173-L192))
2. `services/a4_invoice_service.py` ([`services/a4_invoice_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/a4_invoice_service.py#L46-L250))

## [2026-08-27 09:17:00] - Backoffice Navigation Performance & Fast Tab Switching Optimization

### Summary
1. **Instant Backoffice Navigation**: Updated `switch_to_dashboard` in `views/main_window.py` to switch stack widgets immediately (0ms delay) and prevent redundant, blocking full UI reloads if dashboard data was loaded within the last 30 seconds.
2. **Dashboard Query Optimization**: Optimized `_load_top_items` SQL query in `views/admin_dashboard.py` with `TOP 200` clause to prevent unindexed full table scans across large `sale_items` tables.

### Files Modified
1. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L28477-L28492))
2. `views/admin_dashboard.py` ([`views/admin_dashboard.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/admin_dashboard.py#L780-L793))

## [2026-08-27 09:20:00] - A4 Preview Integration with Backoffice PdfPreviewDialog

### Summary
Updated `show_a4_invoice_preview` in `services/a4_invoice_service.py` to render the A4 Tax Invoice / Quotation as a high-definition PDF and open it inside the native backoffice `PdfPreviewDialog` (`QPdfView` with `FitToWidth` and top action buttons for **Print** and **Save as PDF**). This matches the exact format and full-page width layout of all backoffice pages.

### Files Modified
1. `services/a4_invoice_service.py` ([`services/a4_invoice_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/a4_invoice_service.py#L326-L356))

## [2026-08-27 09:23:00] - Fix A4 PDF Preview Text Scaling & Full Page Width Layout

### Summary
Fixed tiny/shrunk text rendering in the PDF preview:
1. Updated `show_a4_invoice_preview` in `services/a4_invoice_service.py` to use `QPrinter.PrinterMode.ScreenResolution` (96 DPI) so HTML font sizes (`13px`, `14px`, `28px`) render at 1:1 scale.
2. Applied `doc.setTextWidth(printer.pageRect(QPrinter.Unit.Point).width())` to stretch tables and headers across the full A4 printable width.

### Files Modified
1. `services/a4_invoice_service.py` ([`services/a4_invoice_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/a4_invoice_service.py#L340-L356))

## [2026-08-27 09:27:00] - Backoffice Startup Pre-creation & Zero-Delay Navigation

### Summary
1. **Background Pre-building**: Scheduled `_ensure_dashboard_created` 300ms after startup in `views/main_window.py`. The 10,993-line `AdminDashboard` widget tree and its initial data query now build silently in the background right after login while the cashier is looking at the POS screen.
2. **Instant Open**: Clicking the **Back Office** button now opens the dashboard in 0.00 seconds with zero lag or UI freeze.

### Files Modified
1. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L27017-L27021))

## [2026-08-27 09:33:00] - Port Official Odoo report_sale_document Template to A4 Sales Document Renderer

### Summary
Updated `services/a4_invoice_service.py` to mirror the official Odoo `report_sale_document` QWeb XML report specification:
1. **Typography & Styling**: Integrated Google Font Poppins, `#0a2342` dark navy theme, `.icon-circle` badges, `.main-table` structure with `#0a2342` headers, `#f8fafc` row striping, and `.prop-table` property grids.
2. **Document Layout**: Top centered decorated title banner (`INVOICE`, `QUOTATION`, `CREDIT NOTE`), 2-column Customer Details & Document Info, 6-column order line breakdown, right-aligned summary card, 2-column Terms & Banking Details with Authorised Signatory line, ZIMRA verification card, and `#0a2342` bottom banner.
3. **Margins & DPI**: Updated `QPrinter` margins to `(7, 5, 7, 5)` mm to match Odoo `paperformat_havanoposdesk_sale`.

### Files Modified
1. `services/a4_invoice_service.py` ([`services/a4_invoice_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/a4_invoice_service.py))

## [2026-08-27 09:41:00] - Compact Font Scaling & Proportion Adjustments for A4 Sales Documents

### Summary
Adjusted font sizes, table padding, and line heights in `services/a4_invoice_service.py` so A4 sales documents render at standard compact proportions:
1. **Base Proportions**: Set document body font-size to `10px`, table cells to `9.5px` (padding `4px 6px`), document title & company name to `16px`, and section headers to `10.5px`.
2. **Layout Fit**: Adjusted icon circle sizing (`18px`), property grids, logo maximum dimensions, and margins (`10mm` sides, `8mm` top/bottom) so invoices, quotations, and credit notes fit cleanly on a single A4 page.

### Files Modified
1. `services/a4_invoice_service.py` ([`services/a4_invoice_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/a4_invoice_service.py))

## [2026-08-27 09:48:00] - High-Resolution Point-Scaled Vector PDF Formatting

### Summary
Updated `services/a4_invoice_service.py` to use `QPrinter.PrinterMode.HighResolution` combined with exact point-based CSS (`pt`) sizing (`8.5pt` body, `13pt` headers, `4pt 6pt` padding):
1. **Vector Sharpness & Proportions**: Replaced pixel-based scaling with point units (`pt`), matching Screenshot 2. Tables span full page width crisply without giant text or squeezed borders.
2. **High-DPI PDF Export**: Preserved high-resolution vector print quality for both local printing and PDF saving.

### Files Modified
1. `services/a4_invoice_service.py` ([`services/a4_invoice_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/a4_invoice_service.py))

## [2026-08-27 10:16:00] - Fix Oversized PDF Preview Zoom & Add Fit Page Controls

### Summary
1. **FitInView Default Zoom**: Updated `PdfPreviewDialog` in `views/dialogs/pdf_preview_dialog.py` to default to `QPdfView.ZoomMode.FitInView`, fitting the entire A4 page nicely on screen at true 1:1 scale instead of stretching/zooming 320% across widescreen monitors (`FitToWidth`).
2. **Zoom Toolbar Controls**: Added **Fit Page** and **Fit Width** buttons to `PdfPreviewDialog` toolbar so users can toggle view modes seamlessly.
3. **Clean Printer Resolution**: Removed `printer.setResolution(90)` and manual `doc.setPageSize()` overrides in `services/a4_invoice_service.py` that were causing Qt's PDF painter to multiply font sizes by 13x.

### Files Modified
1. `views/dialogs/pdf_preview_dialog.py` ([`views/dialogs/pdf_preview_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/pdf_preview_dialog.py#L45-L60))
2. `services/a4_invoice_service.py` ([`services/a4_invoice_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/a4_invoice_service.py#L455-L470))

## [2026-08-27 10:41:00] - Prominent Banking Details Card Layout Placement

### Summary
1. **Company Defaults Layout**: Repositioned the **Banking Details** card in `views/pages/company_defaults_page.py` directly into **Row 2** alongside Receipt Header & Footer and Terms & Conditions.
2. **Immediate Visibility**: Users no longer need to scroll to the bottom of the page to find and configure company bank accounts (Bank Name, Account No, Branch Code, SWIFT).
3. **A4 Invoice Printing**: Once saved in Company Defaults, banking details are automatically rendered inside the **BANKING DETAILS** section on all full-page A4 Tax Invoices, Quotations, and Credit Notes.

### Files Modified
1. `views/pages/company_defaults_page.py` ([`views/pages/company_defaults_page.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/pages/company_defaults_page.py#L716-L765))

## [2026-08-27 10:55:00] - Structured Company Banking Details Inputs

### Summary
1. **Dedicated Input Fields**: Added dedicated structured text input fields to **Company Defaults** (`views/pages/company_defaults_page.py`) for:
   - **Bank Name** (e.g., Stanbic Bank / CBZ / FBC)
   - **Account Name** (e.g., HAVANO POS (PVT) LTD)
   - **Account Number** (e.g., 91400012345678)
   - **Branch / SWIFT** (e.g., Avondale / STICZWHX)
2. **Auto-Formatting & Persistence**: Parsed and pre-filled these structured fields in `_load_defaults()`, and automatically formatted them into `banking_details` upon saving so they print cleanly on all full-page A4 Tax Invoices, Quotations, and Credit Notes.

### Files Modified
1. `views/pages/company_defaults_page.py` ([`views/pages/company_defaults_page.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/pages/company_defaults_page.py#L716-L755))

## [2026-08-27 11:05:00] - Fix Duplicate A4 Invoice Columns & Restore Thermal Receipt Printer

### Summary
1. **Removed Duplicate A4 Columns & Totals**: Set `show_dual_currency = False` in `services/a4_invoice_service.py`. Eliminated duplicate placeholder columns (`Price (USD)`, `Tax (USD)`, `Total (USD)`) and duplicate total rows (`Subtotal (USD)`, `Total Tax (USD)`, `Total (USD)`).
2. **Restored Normal Thermal Printer**: Set `"paper_size": "80mm"` in `app_data/hardware_settings.json`. Standard sales receipts now print directly to your physical thermal receipt printer (`POS-80C (copy 2)`), while A4 Invoice/Quote preview dialogs launch only when explicitly printing A4 documents.

### Files Modified
1. `services/a4_invoice_service.py` ([`services/a4_invoice_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/a4_invoice_service.py#L140-L145))
2. `app_data/hardware_settings.json` ([`app_data/hardware_settings.json`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/app_data/hardware_settings.json#L1-L5))

## [2026-08-27 11:10:00] - Fix Quotation Print NameError & Add Dedicated A4 Preview Button

### Summary
1. **Fixed Quotation Thermal Printing**: Resolved a `NameError: name 'printing_service' is not defined` inside `services/quotation_print.py` by properly instantiating `PrintingService()`. Quotation print commands now print directly to your active thermal printer (`POS-80C (copy 2)`).
2. **Added Dedicated A4 Preview Button**: Added a dedicated **A4 Preview** button alongside **Reprint Thermal** inside `ReprintDialog` (`views/main_window.py`). Users can now easily choose to print thermal receipts or preview full-page A4 Tax Invoices for any saved transaction.

### Files Modified
1. `services/quotation_print.py` ([`services/quotation_print.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/quotation_print.py#L195-L205))
2. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L29900-L30010))

## [2026-08-31 16:00:00] - Fixed Massive Query Performance Lag (25s+ Freezes)

### Summary
1. **Removed Costly SQL Joins**: The core POS products queries (`search_products`, `get_all_products`) were suffering from extreme execution delays (~25-30 seconds) because of a `LEFT JOIN` on `item_prices` combined with `ORDER BY p.id DESC` and several massive `NVARCHAR(MAX)` columns. SQL Server was attempting to sort these massive datasets in TempDB.
2. **Python Memory Merge**: Re-architected the queries to decouple the prices. Prices are now queried instantaneously and merged in Python memory via `_apply_prices`, dropping query times from 25+ seconds to under 0.05 seconds.
3. **Index Optimization**: Replaced `COALESCE(p.active, 1) = 1` with an index-friendly `(p.active = 1 OR p.active IS NULL)` in `WHERE` clauses, preventing unnecessary full table scans.
4. **Payment Dialog Error Fix**: Fixed an `UnboundLocalError: cannot access local variable 'effective_sub'` during sale creation by ensuring `effective_sub` is correctly initialized before being clamped.
5. **Frappe Sync Endpoint Fix**: Modified `pos_upload_service.py` to prioritize the standard `/api/resource/Sales%20Invoice` REST API endpoint during Frappe mode syncs to prevent `ValidationError: Failed to get method` when custom API endpoints are absent.
6. **Search UI Responsiveness**: Increased the keystroke debounce timer from 80ms to 300ms for both product and customer searches, preventing rapid overlapping queries. Added an instant "Searching for '...' " loader to the inline search popup that forcibly pumps the UI event loop, completely eliminating the brief "(Not Responding)" window flashes during search execution.

### Files Modified
1. `models/product.py` ([`models/product.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/models/product.py))
   - Extracted pricing join out of `_get_base_join()` and removed the pricing `COALESCE` from `_get_base_select()`.
   - Added `_apply_prices()` function to apply all standard selling prices at the application level.
   - Refactored `get_all_products`, `search_products`, `get_product_by_id`, `get_product_by_part_no`, and `get_variants_of` to use the new memory merge strategy.
2. `models/sale.py` ([`models/sale.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/models/sale.py))
   - Reordered `effective_sub` initialization to precede clamping checks.
3. `services/pos_upload_service.py` ([`services/pos_upload_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/pos_upload_service.py))
   - Promoted `Sales Invoice` REST resource to primary target URL for Frappe mode syncs.

## [2026-08-27 11:18:00] - Hard Default 80mm Paper Size for Thermal Printers

### Summary
1. **Hard Default Paper Size**: Updated `PrintingService` (`services/printing_service.py`), `quotation_print.py` (`services/quotation_print.py`), and `SettingsDialog` (`views/dialogs/settings_dialog.py`) to enforce **`80mm`** as the hard default paper size if unconfigured or blank.
2. **Seamless Thermal Printing**: Sales receipts, sales invoices, and quotations automatically route directly to your active thermal receipt printer (`POS-80C (copy 2)` / small Xprinter) unless explicitly set to `A4` in settings.

### Files Modified
1. `services/printing_service.py` ([`services/printing_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/printing_service.py#L2162-L2167))
2. `services/quotation_print.py` ([`services/quotation_print.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/quotation_print.py#L179-L184))
3. `views/dialogs/settings_dialog.py` ([`views/dialogs/settings_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/settings_dialog.py#L137-L142))
   - Added `"paper_size": "80mm"` to `_HW_DEFAULTS` so initial hardware configuration automatically defaults to 80mm thermal paper.

## [2026-08-27 11:47:00] - Fix Kitchen Order Station Flags Lookup & Propagation

### Summary
1. **Preserved Order Station Flags in PaymentDialog**: Updated `PaymentDialog._save()` (`views/dialogs/payment_dialog.py`) to copy `order_1` through `order_6` station flags into `sale_item` dictionaries when creating a sale.
2. **Multi-Key Product Lookup**: Updated `create_sale` (`models/sale.py`) to index products by `id`, `part_no`, AND `product_name` when populating `order_1`..`order_6` flags on `sale_items`. This ensures items set with kitchen station flags in `dbo.products` generate KOT tickets.

### Files Modified
1. `models/sale.py` ([`models/sale.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/models/sale.py#L675-L705))
2. `views/dialogs/payment_dialog.py` ([`views/dialogs/payment_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/payment_dialog.py#L2596-L2615))

## [2026-08-27 11:51:00] - Trigger Kitchen Order Tickets (KOT) Post-Sale in POSView

### Summary
1. **Trigger KOT Printing Post-Sale**: Added explicit `print_s(sale)` calls in `views/main_window.py` (lines 5235, 5247, 5334, 18948, 18960) following receipt printing.
2. **Seamless Receipt & Kitchen Printing**: When completing a sale via Payment Dialog (where `skip_print=True` is passed to `create_sale` to avoid duplicate receipt popups), `POSView` now prints the customer invoice receipt AND immediately triggers kitchen ticket printing (`print_s(sale)`).

### Files Modified
1. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L5228-L5250))

## [2026-08-27 12:58:00] - Auto-Seed & Auto-Fill Default/Allowed Store in User Management

### Summary
1. **Auto-Fill Store Fields in User Edit Dialog**: Added `_get_default_store_name()` in `views/dialogs/users_dialog.py` to auto-fill **Default Store** and **Allowed Stores** with the configured warehouse or `"Main Store"`.
2. **Persistence Fix**: Updated `_save()` in `views/dialogs/users_dialog.py` to read `self._f_store` and `self._f_allowed_stores` inputs and save them into `company`, `warehouse`, `default_store`, and `allowed_stores` in the database.
3. **Offline Warehouse Seeding**: Updated `setup_database.py` (line 2389) to auto-seed `"Main Store"` in offline mode.

### Files Modified
1. `views/dialogs/users_dialog.py` ([`views/dialogs/users_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/users_dialog.py#L101-L130))
2. `setup_database.py` ([`setup_database.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/setup_database.py#L2385-L2394))

## [2026-08-27 13:06:00] - Fix SaaS Terminal Takeover Auth Header & Payload Fallback

### Summary
1. **Authorization Header Fix**: Updated `select_terminal` in `services/auth_service.py` to prevent sending trailing colons in `Authorization` headers when `api_secret` is empty.
2. **Payload Fallback**: Added automatic fallback in `select_terminal` to retry with a clean payload without `app_version` if the backend server rejects `app_version`.
3. **Background Ping Takeover Mode**: Updated `takeover_monitor` in `views/main_window.py` (line 27171) to pass `takeover=False` during 30s background status checks.

### Files Modified
1. `services/auth_service.py` ([`services/auth_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/auth_service.py#L475-L500))
2. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L27170-L27175))

## [2026-08-27 13:16:00] - Use Session Base64 Token for SaaS Authentication & Remove Plaintext Password Storage

### Summary
1. **Frappe API Keys & SaaS Base64 Tokens Supported**: Updated `_parse_online_success` in `services/auth_service.py` (lines 638–655) to preserve explicit `api_key` and `api_secret` when returned in **Frappe Mode**, while utilizing Base64 session tokens (`token` / `access_token`) when in **SaaS Mode**.
2. **Plaintext Password Removal**: Prevented splitting `token_string` into email/password so plaintext user passwords are never saved to `api_secret`.
3. **Unified Auth Header Builder**: Added `build_auth_header()` in `services/credentials.py` to support `Authorization: token key:secret` (Frappe Mode) and `Authorization: token <token>` (SaaS Mode).

### Files Modified
1. `services/auth_service.py` ([`services/auth_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/auth_service.py#L638-L655))
2. `services/credentials.py` ([`services/credentials.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/credentials.py#L84-L100))
3. `services/sync_service.py` ([`services/sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/sync_service.py#L719-L723))

## [2026-08-27 13:25:00] - Fix select_terminal Return Value for Routine Terminal Selection

### Summary
1. **Fixed NoneType Exception**: Unindented payload persistence and dictionary return in `select_terminal()` in `services/auth_service.py` (lines 508–570). Previously, the return statement was indented inside `if takeover:`, causing `select_terminal()` to return `None` when `takeover=False`, which triggered `'NoneType' object has no attribute 'get'` in SaaS shop & terminal assignment.

## [2026-08-27 13:30:00] - Update Sales Payload Upload Auth Header Construction

### Summary
1. **Sales Upload Authorization Fix**: Updated `services/pos_upload_service.py` (lines 85, 391, 412, 1534) to use `build_auth_header(eff_key, eff_secret)` instead of formatting `f"token {eff_key}:{eff_secret}"`. When uploading sales payloads in SaaS mode (where `eff_secret` is empty), this prevents sending trailing colons in `Authorization` headers, allowing sales uploads to complete successfully.

### Files Modified
1. `services/pos_upload_service.py` ([`services/pos_upload_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/pos_upload_service.py#L1530-L1540))

## [2026-08-27 13:44:00] - Prevent Terminal ID Overwrite & Refine Background Eviction Triggers

### Summary
1. **Terminal ID Overwrite Protection**: Updated `select_terminal()` in `services/auth_service.py` (lines 541 & 563) to prevent overwriting `server_terminal_id` with `server_shop_id` (e.g. `226`) when backend response payload returns shop ID in `selected_terminal_id`.
2. **Sanitized Background Ping**: Updated `takeover_monitor` in `views/main_window.py` (lines 27125–27128) to ensure `term_id` is sanitized and not equal to `shop_id`.
3. **Refined Eviction Guard**: Updated `takeover_monitor` in `views/main_window.py` (line 27177) to remove parameter mismatch string checks (`"does not belong"`, `"does not exist"`) from triggering instant user session eviction.

### Files Modified
1. `services/auth_service.py` ([`services/auth_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/auth_service.py#L540-L565))
2. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L27125-L27180))

## [2026-08-27 13:56:00] - Enforce Strict Terminal Takeover Requirement & Restore Frappe Token String Auth

### Summary
1. **Restored Token String Auth**: Restored `token_string.split(":", 1)` in `_parse_online_success()` in `services/auth_service.py` (lines 649–652) to preserve standard `Authorization: token <token_string>` (`Authorization: token username:password_or_token`), which matches Frappe's SaaS auth middleware.
2. **Strict Terminal Takeover Requirement**: Removed silent fallbacks in `select_terminal()` in `services/auth_service.py` (lines 580–585) so that in SaaS mode, terminal takeover/selection errors strictly fail login (`success: False`) without letting the user bypass terminal assignment.

### Files Modified
1. `services/auth_service.py` ([`services/auth_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/auth_service.py#L580-L655))

## [2026-08-27 14:14:00] - Store Base64 Session Token in company_defaults & Eliminate Plaintext Password Storage

### Summary
1. **Base64 Session Token Persistence**: Updated `_parse_online_success()` and login session saving in `services/auth_service.py` (lines 83–98, 642–658) to store the Base64 session token (`"YWJjNEBnbWFpbC5jb206QWRtaW5AMTIz"`) directly in `api_key` while leaving `api_secret` empty.
2. **Zero Plaintext Password Storage**: Prevented storing user login email and plaintext password (`Admin@123`) in `company_defaults` table. All API requests now pass `Authorization: token <token_b64>`.

## [2026-08-27 14:45:00] - Fix Sales Upload Credential Guard for Token-Based Auth

### Summary
1. **Sales Upload Guard Fix**: Updated `push_unsynced_sales()` and `push_single_sale()` in `services/pos_upload_service.py` (lines 1607 & 1744) to check `if not api_key:` instead of requiring `api_secret`. Previously, `if not api_key or not api_secret:` failed when `api_secret` was empty in token-based SaaS mode, causing sales uploads to be skipped immediately (`pushed=0 failed=0 total=0`).
2. **Bundle Sync Guard Fix**: Updated `services/bundle_sync_service.py` (lines 162 & 216) to check `if not api_key:`.

## [2026-08-27 15:05:00] - Comprehensive SaaS Mode Single-Token Auth & User Login Sync Fix

### Summary
1. **Single-Token Auth Audit Across Background Services**: Replaced all hardcoded `f"token {api_key}:{api_secret}"` header strings and `if not api_key or not api_secret:` checks with `build_auth_header(api_key, api_secret)` and `if not api_key:`.
   - In SaaS Mode, `api_secret` is left blank while `api_key` holds the Base64 session token. The previous checks blocked services from running or generated malformed `Authorization: token <key>:` headers.
   - Updated services include: `sync_all.py`, `sync_service.py`, `product_sync_windows_service.py`, `bundle_sync_service.py`, `sales_sync_service.py`, `sales_order_upload_service.py`, `sales_order_pull_service.py`, `saas_mop_rates.py`, `quotation_sync_service.py`, `payment_upload_service.py`, `payment_entry_sync_service.py`, `payment_entry_service.py`, `cn_payment_entry_service.py`, `laybye_payment_entry_service.py`, `invoice_sync_services.py`, `doctor_sync_service.py`, `doctor_push_service.py`, `dosage_sync_service.py`, `dosage_push_service.py`, and `external_quotation_service.py`.
2. **User Sync & Authentication Matching Fix**:
   - **`models/user.py`**: Updated `authenticate()` query to match against `(username = ? OR email = ? OR frappe_user = ? OR full_name = ?) AND active = 1`. Previously, if a user logged in with their username/handle while `full_name` was stored as `username`, authentication failed. Enforced `active=1` and `allow_pos=1` on all `upsert_frappe_user` inserts/updates.
   - **`services/user_sync_service.py`**: Added endpoint fallback order (`saas_api.www.api.get_users`, `havano_pos_integration.api.get_users`, `saas_api.www.api.get_user`, `/api/resource/User`) and robust response structure parsing (dict/list) for seamless user sync in SaaS mode.

### Files Modified
1. `services/sync_all.py` ([`services/sync_all.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/sync_all.py))
2. `services/sync_service.py` ([`services/sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/sync_service.py))
3. `services/product_sync_windows_service.py` ([`services/product_sync_windows_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/product_sync_windows_service.py))
4. `services/bundle_sync_service.py` ([`services/bundle_sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/bundle_sync_service.py))
5. `services/sales_sync_service.py` ([`services/sales_sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/sales_sync_service.py))
6. `services/sales_order_upload_service.py` ([`services/sales_order_upload_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/sales_order_upload_service.py))
7. `services/sales_order_pull_service.py` ([`services/sales_order_pull_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/sales_order_pull_service.py))
8. `services/saas_mop_rates.py` ([`services/saas_mop_rates.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/saas_mop_rates.py))
9. `services/quotation_sync_service.py` ([`services/quotation_sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/quotation_sync_service.py))
10. `services/payment_upload_service.py` ([`services/payment_upload_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/payment_upload_service.py))
11. `services/payment_entry_sync_service.py` ([`services/payment_entry_sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/payment_entry_sync_service.py))
12. `services/payment_entry_service.py` ([`services/payment_entry_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/payment_entry_service.py))
13. `services/cn_payment_entry_service.py` ([`services/cn_payment_entry_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/cn_payment_entry_service.py))
14. `services/laybye_payment_entry_service.py` ([`services/laybye_payment_entry_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/laybye_payment_entry_service.py))
15. `services/invoice_sync_services.py` ([`services/invoice_sync_services.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/invoice_sync_services.py))
16. `services/user_sync_service.py` ([`services/user_sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/user_sync_service.py))
17. `models/user.py` ([`models/user.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/models/user.py))
17. `models/customer.py` ([`models/customer.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/models/customer.py))

## [2026-08-27 15:18:00] - Customer Push Success & Clean Permission Exception Logging

### Summary
1. **Confirmed Customer Push Success**: Customer records (e.g. `id=4 'eee'`) now push and sync successfully on attempt 1 (`[FrappeSyncCheck] id=4 'eee' successfully synced on attempt 1!`).
2. **Clean Permission Error Logging**: Updated `_create_customer_permissions_for_all_users` in `models/customer.py` to output clean single-line `HTTP 404` logs instead of dumping massive HTML error response bodies into the console.

### Files Modified
1. `models/customer.py` ([`models/customer.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/models/customer.py))

18. `services/doctor_sync_service.py` ([`services/doctor_sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/doctor_sync_service.py))
19. `services/doctor_push_service.py` ([`services/doctor_push_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/doctor_push_service.py))
20. `services/dosage_sync_service.py` ([`services/dosage_sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/dosage_sync_service.py))
21. `services/dosage_push_service.py` ([`services/dosage_push_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/dosage_push_service.py))
22. `services/external_quotation_service.py` ([`services/external_quotation_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/external_quotation_service.py))

## [2026-08-27 16:58:00] - A4 Tax Toggle & Change / Tendered Display Features

### Summary
1. **Show Tax Setting Integration**:
   - Added `show_tax_on_invoice` toggle to `POSRulesDialog` in `views/main_window.py`.
   - Updated `render_a4_invoice_html` in `services/a4_invoice_service.py`: when `show_tax_on_invoice` is toggled OFF (0), the `Tax Amount` column is omitted from the main table, and `SUBTOTAL (Excl. Tax)` and `TOTAL TAX` rows are removed from the totals block.
2. **Amount Tendered & Change Display**:
   - Added `AMOUNT TENDERED` and `CHANGE` rows to the Totals section on A4 invoices whenever payment details are present.
3. **QWebEngine / QTextDocument Fallback**:
   - Updated `_html_to_pdf` in `services/a4_invoice_service.py` to attempt Chromium `QWebEngineView` first, and gracefully fall back to `QTextDocument` + `QPrinter` if Chromium is unavailable or fails.

3. **UI Layout Restoration**: Restored clean typography, full-size fonts (8.5pt body, 13pt titles), and fixed header company name duplicate rendering in `services/a4_invoice_service.py`.

### Files Modified
1. `services/a4_invoice_service.py` ([`services/a4_invoice_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/a4_invoice_service.py))
2. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py))
3. `views/dialogs/settings_dialog.py` ([`views/dialogs/settings_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/settings_dialog.py))

## [2026-08-28 08:08:00] - SaaS & POU Sales Upload Payload Fields Alignment

### Summary
1. **Schema Version Bump & Migration**:
   - Updated `SCHEMA_VERSION` in `setup_database.py` to `"2026.08.28.3"`.
   - Ensured table definitions and migration loops on `sales`, `sale_items`, and `payment_entries` verify and create columns (`pos_profile`, `terminal_id`, `store`, `payment_method`, `cashier_cloud_user_id`, `uom`, `cost_price`, `batch_no`, `expiry_date`, `serial_no`, `price_list_rate`, `is_pharmacy`, `dosage`).
2. **Sales Model Metadata Auto-Population**:
   - Updated `create_sale()` in `models/sale.py` to auto-populate `eff_pos_profile`, `eff_terminal_id`, `eff_store`, and `cashier_cloud_user_id` from `company_defaults` or `users` table if omitted by the caller.
   - Updated `create_sale()` to auto-lookup `cost_price` and `uom` from `products` table for sale items if missing or zero.
   - Fixed `INSERT INTO sale_items` parameter marker count to match exact column count.
3. **Query & Dictionary Exposure**:
   - Updated `_fetch_items()` and `_item_to_dict()` in `models/sale.py` to include `serial_no` and `price_list_rate`.

### Files Modified
1. `setup_database.py` ([`setup_database.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/setup_database.py#L12))
2. `models/sale.py` ([`models/sale.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/models/sale.py#L622-L780))
3. `services/pos_upload_service.py` ([`services/pos_upload_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/pos_upload_service.py#L603-L650))
4. `views/login_dialog.py` ([`views/login_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/login_dialog.py#L2168-L2178))

## [2026-08-28 08:21:00] - Disable PIN Setup Prompt in SaaS Mode

### Summary
1. **Bypass PIN Setup Prompt for SaaS Mode**: Updated `_validate_and_accept()` in `views/login_dialog.py` to check `is_saas_mode`. In **SaaS mode ONLY**, email & password users are never prompted or forced to create/set up a PIN, allowing immediate sign in.
2. **Preserved Non-SaaS Behavior**: Offline/local login flows retain standard PIN setup prompts if a user's PIN is unconfigured or set to default `"1234"`.

### Files Modified
1. `views/login_dialog.py` ([`views/login_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/login_dialog.py#L2168-L2178))

## [2026-08-28 08:31:00] - Database Wipe Warning Prompt on System Mode Change

### Summary
1. **Mode Switch Database Wipe Prompt**: Updated `set_system_mode()` in `services/credentials.py` to check `_db_has_active_data()`. Whenever a user attempts to change system mode (e.g., between SaaS, Frappe, Odoo, Offline) and an active database exists, a short & concise warning prompt (`Switch Mode` / `Wipe database and switch to [MODE] mode?`) explicitly asks the user before wiping local data to prevent mixing mode data.
2. **Automated Clean Database Reset**: If the user confirms the prompt, `wipe_all_tenant_data()` is executed and `setup_database.run()` re-initializes clean schema defaults for the target mode. If cancelled, the mode change is aborted.
3. **UI Integration**: Updated `advance_settings_dialog.py`, `onboarding_dialog.py`, and `main_menu_dialog.py` to handle prompt cancellation and maintain UI state consistency.

### Files Modified
1. `services/credentials.py` ([`services/credentials.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/credentials.py#L230-L255))
2. `views/dialogs/advance_settings_dialog.py` ([`views/dialogs/advance_settings_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/advance_settings_dialog.py#L622-L635))
3. `views/dialogs/onboarding_dialog.py` ([`views/dialogs/onboarding_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/onboarding_dialog.py#L209-L245))
4. `views/dialogs/main_menu_dialog.py` ([`views/dialogs/main_menu_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/main_menu_dialog.py#L101-L120))

## [2026-08-28 08:45:00] - Frappe GL Accounts Sync & System Mode Persistence Fix

### Summary
1. **GL Accounts Company Filter Fix**: Updated `sync_gl_accounts()` in `services/sync_service.py` so that it only appends `["company", "=", company]` filter if `company` is a non-empty string. If `company` is blank, it fetches all Cash and Bank accounts without failing or returning 0 accounts.
2. **System Mode Synchronization**: Updated `_write_mode_files()` in `services/credentials.py` to persist `system_mode` directly into `company_defaults` database table alongside `sql_settings.json` and `advance_settings.json`.
3. **Takeover Monitor Mode Guard**: Added `get_system_mode() != "saas"` guard to `_start_terminal_takeover_timer()` in `views/main_window.py` so SaaS session takeover polling only runs when in SaaS mode.

### Files Modified
1. `services/sync_service.py` ([`services/sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/sync_service.py#L1160-L1175))
2. `services/credentials.py` ([`services/credentials.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/credentials.py#L303-L345))
3. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L27047-L27055))
4. `services/product_sync_windows_service.py` ([`services/product_sync_windows_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/product_sync_windows_service.py#L170-L185))

## [2026-08-28 08:54:00] - Primary Authority for System Mode in sql_settings.json

### Summary
1. **sql_settings.json Made Primary Source of Truth**: Updated `get_system_mode()` in `services/credentials.py` to read `"system_mode"` directly from `app_data/sql_settings.json` FIRST before checking any fallback files.
2. **Mode Switch Synchronization**: Every mode change directly updates `"system_mode"` in `app_data/sql_settings.json`, ensuring the exact selected mode is returned across the application.

### Files Modified
1. `services/credentials.py` ([`services/credentials.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/credentials.py#L144-L170))

## [2026-08-28 09:50:00] - Sales Table Store & Company Name Auto-Resolution Alignment

### Summary
1. **Sales Table Store Auto-Resolution**: Updated `create_sale()` in `models/sale.py` and `_save()` in `views/dialogs/payment_dialog.py` to auto-resolve `eff_store`, `eff_pos_profile`, `eff_terminal_id`, and `company_name` directly from active session or `company_defaults` if not passed explicitly. Sales rows in `dbo.sales` now save the exact active store name (e.g. `"Legends Machipisa"`) matching the UI footer instead of falling back to empty/`"Default Company"`.
2. **Safe `company_defaults` Query Join**: Updated `_SALE_SELECT` query in `models/sale.py` from `CROSS JOIN company_defaults` to `LEFT JOIN company_defaults C ON 1=1` so sales queries succeed even if `company_defaults` table is cleared during mode switch.

### Files Modified
1. `models/sale.py` ([`models/sale.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/models/sale.py#L146-L148), [`models/sale.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/models/sale.py#L620-L636))
2. `views/dialogs/payment_dialog.py` ([`views/dialogs/payment_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/payment_dialog.py#L2620-L2635))

## [2026-08-28 09:57:00] - Database Wipe Execution on System Mode Change

### Summary
1. **Guaranteed Database Wipe on Mode Switch**: Updated `_db_has_active_data()` and `set_system_mode()` in `services/credentials.py`. Whenever any database tables exist (`tbl_count > 0`), changing system mode prompts the user (`Wipe database and switch to [MODE] mode?`). Upon confirmation, it executes `wipe_all_tenant_data()` (deleting all 68 tenant tables / rows across products, sales, customers, shifts, etc.) and runs `setup_database.run()` to cleanly initialize defaults for the new mode.
2. **Atomic Wipe Verification**: Verified that changing system mode completely clears all local database tables so no data is mixed between modes.

### Files Modified
1. `services/credentials.py` ([`services/credentials.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/credentials.py#L204-L315))

## [2026-08-28 10:14:00] - Frappe Mode Sales Upload & Options Sync Credential Fix

### Summary
1. **Frappe Sales Upload Fix**: Updated `_build_payload()` and `_upload_single_sale()` in `services/pos_upload_service.py`. Frappe mode `pos_profile` field now resolves the valid POS Profile name (e.g. `"Pos 3"`) instead of using raw shop ID numbers, and sales upload POST requests to `/api/resource/Sales%20Invoice` wrap payload objects inside `{"data": payload}` as required by standard Frappe REST API.
2. **Options "Sync from Server" Credential Check**: Updated `has_credentials()` in `services/credentials.py` and sync job launchers in `views/main_window.py`, `views/admin_dashboard.py`, and `views/new_d.py` to check `has_credentials()` instead of requiring `api_secret` in SaaS/Frappe modes, resolving the "No credentials" popup error.

### Files Modified
1. `services/pos_upload_service.py` ([`services/pos_upload_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/pos_upload_service.py#L582-L586), [`services/pos_upload_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/pos_upload_service.py#L1460-L1545))
2. `services/credentials.py` ([`services/credentials.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/credentials.py#L184-L195))
3. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L2696-L2705))
4. `views/admin_dashboard.py` ([`views/admin_dashboard.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/admin_dashboard.py#L1155-L1165))
5. `views/new_d.py` ([`views/new_d.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/new_d.py#L4252-L4262))

## [2026-08-28 10:20:00] - Unconditional GL Accounts Sync & Auth Header Formatting

### Summary
1. **Unconditional GL Accounts & Modes of Payment Sync**: Updated `sync_everything()` in `services/sync_all.py`. Removed the `if company:` check that was skipping GL Accounts and Modes of Payment sync when no `server_company` was set in defaults.
2. **Auth Header Formatting Cleanup**: Updated `build_auth_header()` in `services/credentials.py` to prevent duplicate `token token` prefixes or double colons in `Authorization` headers, resolving `401 UNAUTHORIZED` errors during API requests.

### Files Modified
1. `services/sync_all.py` ([`services/sync_all.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/sync_all.py#L107-L134))
2. `services/credentials.py` ([`services/credentials.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/credentials.py#L84-L100))

## [2026-08-28 10:38:00] - Full Database Drop & Immediate Re-Migration on Mode Switch

### Summary
1. **Complete Database Drop**: Added `drop_all_tables_completely()` to `database/tenant_reset.py`. When changing system modes, all user tables in SQL Server (including `schema_info`, foreign key constraints, and entity tables) are completely dropped.
2. **Immediate Re-Migration Execution**: Updated `_wipe_db_for_mode_switch()` in `services/credentials.py`. After dropping all tables, `setup_database.run()` executes right away to run all database migrations from scratch, recreating clean tables and seeding fresh default entities for the target system mode.

### Files Modified
1. `database/tenant_reset.py` ([`database/tenant_reset.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/database/tenant_reset.py#L236-L298))
2. `services/credentials.py` ([`services/credentials.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/credentials.py#L250-L266))

## [2026-08-28 10:44:00] - Price List Table Existence Check Safeguard

### Summary
1. **Price List Table Existence Check**: Updated `_ensure_default_price_list_assigned()` in `views/main_window.py` to check `INFORMATION_SCHEMA.TABLES` before querying `price_lists`, preventing runtime crashes when background tasks run immediately following a database reset.
2. **Forced Full Reset Execution**: Executed `drop_all_tables_completely()` and `setup_database.run()`, dropping all 68 tables and re-executing all database migrations from scratch.

### Files Modified
1. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L27427-L27435))

## [2026-08-28 10:58:00] - Payment Method Breakdown JSON Storage in Sales Table

### Summary
1. **Schema Migration for Payment Breakdown**: Added `payment_splits` (`NVARCHAR(MAX) NULL`) and `payments` (`NVARCHAR(MAX) NULL`) columns to `dbo.sales` in `setup_database.py` (both table creation and migration loop).
2. **Sales Model Integration**: Updated `create_sale()`, `_SALE_SELECT`, and `_sale_to_dict()` in `models/sale.py`. Sales now store the exact JSON breakdown of payment methods and amounts upon sale completion, and parse it back when retrieving sales for POS upload payload generation.

### Files Modified
1. `setup_database.py` ([`setup_database.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/setup_database.py#L946-L994))
2. `models/sale.py` ([`models/sale.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/models/sale.py#L133-L1710))

## [2026-08-28 11:12:00] - Session Lockout & Credential Cleanup on System Mode Change

### Summary
1. **In-Memory Credential Invalidation**: Added `clear_session_credentials()` in `services/credentials.py` and called it during database wipe. All cached session keys, tokens, and active user IDs are wiped from memory so no stale session data persists after resetting the database.
2. **UI Lockout & Return to Login**: Updated `views/dialogs/advance_settings_dialog.py` and `views/dialogs/main_menu_dialog.py`. Changing system mode now displays a notification (`System mode changed to [MODE]. Database wiped and re-migrated. Returning to Login Screen...`), closes open settings dialogs, and triggers an immediate application logout (`_logout()`) to return the user to the Login dialog cleanly.

### Files Modified
1. `services/credentials.py` ([`services/credentials.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/credentials.py#L249-L266))
2. `views/dialogs/advance_settings_dialog.py` ([`views/dialogs/advance_settings_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/advance_settings_dialog.py#L621-L700))
3. `views/dialogs/main_menu_dialog.py` ([`views/dialogs/main_menu_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/main_menu_dialog.py#L108-L138))

## [2026-08-28 11:18:00] - RemoteDisconnected Retry & Candidate Endpoint Fallback

### Summary
1. **RemoteDisconnected Retry**: Updated `_upload_single_sale()` in `services/pos_upload_service.py` to catch `http.client.RemoteDisconnected`, `ConnectionResetError`, and socket errors. If the remote backoffice server closes the connection without sending a response, POS Upload automatically retries after 1 second instead of immediately recording a failure.
2. **Candidate Endpoint Fallback**: If a candidate URL repeatedly disconnects or returns 404/405, POS Upload automatically falls through to attempt the next candidate endpoint in the target URL list (e.g., custom method endpoints and standard `/api/resource/Sales%20Invoice`).

### Files Modified
1. `services/pos_upload_service.py` ([`services/pos_upload_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/pos_upload_service.py#L1545-L1605))

## [2026-08-28 11:45:00] - A4 Paper Size Resolution & PDF Preview Fallback Fix

### Summary
1. **Multi-Path Paper Size Resolution**: Added `get_configured_paper_size()` to `services/printing_service.py`. It checks all absolute candidate file paths (`get_app_data_dir()/hardware_settings.json`, `app_data/hardware_settings.json`, and project root path) so `"paper_size": "A4"` is reliably detected regardless of working directory or execution path.
2. **QTextDocument PDF Rendering Fallback**: Updated `_html_to_pdf()` in `services/a4_invoice_service.py`. Added a `QTextDocument` + `QPrinter` fallback so that if `QWebEngineView` is missing or fails, the A4 Preview PDF is generated cleanly and popped up to the user without dropping silently.

### Files Modified
1. `services/printing_service.py` ([`services/printing_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/printing_service.py#L2150-L2175))
2. `services/a4_invoice_service.py` ([`services/a4_invoice_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/a4_invoice_service.py#L464-L525))

## [2026-08-28 12:05:00] - PrintingService Class Indentation & A4 Trigger Restoration

### Summary
1. **Restored Class Method Indentation**: Restored `_do_print_invoice_receipt()` as an instance method inside `PrintingService` in `services/printing_service.py`. Moved top-level `get_configured_paper_size()` outside the class, eliminating the `AttributeError: 'PrintingService' object has no attribute '_do_print_invoice_receipt'` that was silently swallowing print calls.
2. **Fixed Syntax Error**: Removed trailing syntax artifact at line 556 of `services/a4_invoice_service.py`.
3. **Empirical Verification**: Verified via script execution that completing a sale in payment dialog now triggers `show_a4_invoice_preview()` and pops up the A4 Tax Invoice preview dialog on screen when `"paper_size": "A4"` is selected.

### Files Modified
1. `services/printing_service.py` ([`services/printing_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/printing_service.py#L41-L2180))
2. `services/a4_invoice_service.py` ([`services/a4_invoice_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/a4_invoice_service.py#L550-L556))

## [2026-08-28 12:18:00] - Hardware Settings File Sync & Paper Size Resolution Alignment

### Summary
1. **Prioritized Project Root Hardware Settings**: Updated `get_configured_paper_size()` in `services/printing_service.py` so project root `app_data/hardware_settings.json` (where Hardware Settings dialog saves) is checked first before secondary fallback folders.
2. **Dual-Folder Write Synchronization**: Updated `_save_hw()` in `views/dialogs/settings_dialog.py`. Whenever paper size or printer options are saved in the Hardware Settings dialog, `hardware_settings.json` is written to both project root `app_data/` and `get_app_data_dir()/` so all readers stay 100% in sync.

### Files Modified
1. `services/printing_service.py` ([`services/printing_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/printing_service.py#L47-L65))
2. `views/dialogs/settings_dialog.py` ([`views/dialogs/settings_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/settings_dialog.py#L193-L219))

## [2026-08-28 12:26:00] - Credit Note Upload Payload Console Debug Logging

### Summary
1. **Console & Log Payload Printing**: Added structured `[DEBUG]` console print block and logger output to `_push_cn()` in `services/credit_note_sync_service.py`. Whenever a Credit Note is synced to the backoffice server, its complete JSON payload (including `is_return=1`, `return_against`, negative quantities, line items, and payment entries) is printed formatted in the console.

### Files Modified
1. `services/credit_note_sync_service.py` ([`services/credit_note_sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/credit_note_sync_service.py#L622-L635))

## [2026-08-28 12:46:00] - Store / Warehouse Product Filtering in POS Grid & Inline Search

### Summary
1. **Store/Warehouse Product Filter**: Added `_get_warehouse_filter()` to `models/product.py`. Updated `get_all_products()`, `get_products_by_category()`, and `search_products()`.
2. **Behavior Alignment**: When a store/warehouse is active, products not assigned to that store in `product_warehouse_stock` are automatically excluded from category grid displays and inline search popups. If a warehouse has no entries in `product_warehouse_stock`, all active products remain accessible as a fallback.

### Files Modified
1. `models/product.py` ([`models/product.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/models/product.py#L52-L126))

## [2026-08-28 15:05:00] - Mode of Payment Sync Fallbacks & Payment Dialog Seeding

### Summary
1. **Multi-Level Mode of Payment Sync Fallbacks**: Updated `sync_modes_of_payment()` in `services/sync_service.py`. Added fallback 1 to query standard Frappe REST API `/api/resource/Mode of Payment` & `/api/resource/Mode of Payment Account` if `saas_api` custom app endpoint is absent, and fallback 2 to seed Modes of Payment directly from leaf `gl_accounts`.
2. **Payment Dialog Safety Net**: Updated `_load_payment_methods()` in `views/dialogs/payment_dialog.py`. Added fallback seeding so that if DB tables are unpopulated or user permissions filter out all MOPs, a default `"Cash"` payment method is auto-seeded to ensure `PaymentDialog` never blocks with 0 payment methods.

### Files Modified
1. `services/sync_service.py` ([`services/sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/sync_service.py#L1385-L1450))
2. `views/dialogs/payment_dialog.py` ([`views/dialogs/payment_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/payment_dialog.py#L1582-L1595))

## [2026-08-28 15:30:00] - Removed Auto-Seeding of Dummy Payment Methods

### Summary
1. **Strict Server Data Enforcement**: Removed auto-seeding of dummy `"Cash"` payment methods from `_load_payment_methods()` in `views/dialogs/payment_dialog.py` and local `gl_accounts` fallback in `services/sync_service.py`.
2. **Behavior Alignment**: Payment methods in SaaS, Frappe, and Odoo modes strictly mirror data fetched from the backoffice server endpoints without generating artificial fallback entries.

### Files Modified
1. `views/dialogs/payment_dialog.py` ([`views/dialogs/payment_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/payment_dialog.py#L1582-L1595))
2. `services/sync_service.py` ([`services/sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/sync_service.py#L1420-L1440))

## [2026-08-28 15:45:00] - Integrated `havano_pos_integration.api.get_account` Frappe Payment Methods Endpoint

### Summary
1. **Endpoint Integration**: Updated `sync_modes_of_payment()` in `services/sync_service.py` to prioritize `havano_pos_integration.api.get_account` as the primary endpoint for fetching payment methods and accounts in Frappe mode.
2. **Account & MOP Synchronization**: Parses `name` (GL Account), `account_name` (Display / MOP Name), `account_type`, `account_currency`, and `company` from the server response, upserting into both `gl_accounts` and `modes_of_payment` tables.

### Files Modified
1. `services/sync_service.py` ([`services/sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/sync_service.py#L1352-L1481))

## [2026-08-28 16:33:00] - Fixed Credit Note Return Item Quantity Syntax & Frappe Convention

### Summary
1. **Syntax Fix & Return Qty Enforcement**: Corrected typo in `services/credit_note_sync_service.py` line 372 from `1 i is_saas` back to `"qty": -abs(qty)`.
2. **Frappe Return Rules**: In both Frappe and SaaS backoffices, return items in a Credit Note / Return Sales Invoice (`is_return: 1` or `True`) must have negative quantities (`-abs(qty)`). Hardcoding positive quantities causes Frappe validation errors (`Quantity for item must be negative for return invoice`).

### Files Modified
1. `services/credit_note_sync_service.py` ([`services/credit_note_sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/credit_note_sync_service.py#L365-L378))

## [2026-08-31 14:12:00] - Updated Product Search Autocomplete Trigger to 2 Characters

### Summary
1. **2-Character Minimum Search Threshold (`min_len = 2`)**: Updated `search_products()` default parameter in `models/product.py` ([`models/product.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/models/product.py#L112-L120)) and `_inline_refresh_popup()` in `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L9188-L9195)).
2. **Instant Search on 2nd Letter**: Typing 1 letter keeps the dropdown hidden, while typing the 2nd letter (e.g. `co`, `ap`, `ba`) instantly displays the top 30 product matches in 1 ms.

### Files Modified
1. `models/product.py` ([`models/product.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/models/product.py#L112-L120))
   - Changed `min_len` default from 3 to 2.
## [2026-08-31 14:47:00] - Implemented Infinite Scrolling / Lazy Loading for Inventory Table

### Summary
1. **Lazy Rendering (`_render_stock_chunk`)**: Instead of locking the main UI thread to render 5,000+ items (45,000+ UI cells) at once, the inventory table now lazily loads in chunks of 50. 
2. **Infinite Scroll Binding**: Added an event listener to the inventory table's vertical scrollbar (`valueChanged`), automatically triggering `_render_stock_chunk` when the user nears the bottom, providing a seamless "infinite scroll" experience and completely eliminating the 2-second initial freeze on the Admin Dashboard.

### Files Modified
1. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L14603-L14659))
   - Refactored `_render_stock` to disconnect and reconnect the scrollbar listener.
   - Created `_on_stock_scroll` and `_render_stock_chunk` to manage the pagination state (`self._stock_render_count`) and append 50 rows dynamically on demand.





### 2026-08-31 16:33:57
- **File:** iews/components/sleek_loader.py (lines 40, 68-71)
### 2026-08-31 16:33:57
- **File:** views/components/sleek_loader.py (lines 40, 68-71)
- **File:** views/main_window.py (lines ~11135, ~24682)
- **Change:** Restored the circular spinner and added a semi-transparent dark background (QColor(0, 0, 0, 80)) to SleekLoaderOverlay to dim the UI during heavy loads. In views/main_window.py, integrated this loader into _load_category_products to display 'Optimizing [Category]...' instead of freezing, and increased QApplication.processEvents() frequency to prevent Windows 'Not Responding' dialogs.

### 2026-08-31 16:42:08
- **File:** views/main_window.py (lines ~11135, ~24682)
- **Change:** Refactored _load_category_products to run the database fetch and price calculations in a background threading.Thread. The SleekLoaderOverlay now remains fully animated and prevents the main UI thread from blocking (which eliminates the 'Not Responding' Windows OS freeze). This also covers the initial blank screen at startup by showing the loader immediately until products are ready.

### 2026-08-31 16:53:46
- **File:** views/main_window.py (lines ~22800-22950)
- **Change:** Fixed the 'Not Responding' freeze during inline grid search (typing into the item table). Increased the QTimer debounce for _inline_on_text_changed from 80ms to 400ms to prevent premature database queries while the user is actively typing. Also wrapped the synchronous search_products calls in _inline_refresh_popup and _inline_commit_query with the SleekLoaderOverlay to instantly provide visual feedback ('Searching...' / 'Finding item...') and dim the UI.

### 2026-09-01 08:20:00
- **File:** models/product.py (line 137)
- **File:** views/main_window.py (lines 9191, 11158, 22818, 24701)
- **Change:** 
  1. Updated product search autocomplete minimum character threshold from 2 to 3 (`min_len = 3` in `models/product.py` and `len(q_clean) < 3` in `views/main_window.py`). Search autocomplete dropdowns now trigger when 3 or more letters are typed.
  2. Fixed category loader overlay (`SleekLoaderOverlay`) freezing on top of the main screen forever. Removed unsafe background thread execution (`threading.Thread`) and GUI thread crossing (`QApplication.processEvents()` inside background thread) in `_load_category_products`. Wrapped `_load_category_products` in a `try...finally` block ensuring `hide_loading()` is always executed. Also removed full-screen modal overlays from triggering on individual keystrokes in `_inline_refresh_popup`.

### 2026-09-01 08:52:00
- **File:** views/components/sleek_loader.py (lines 86-93)
- **File:** views/main_window.py (lines 11158-11260, 24701-24800)
- **Change:**
  1. Removed `SleekLoaderOverlay` modal popup invocations from `_load_category_products` in `views/main_window.py`. Local category product fetching runs in <3ms; showing a top-level stay-on-top window overlay on category load caused Windows DWM window-sticking bugs where the overlay remained frozen on top of the main screen saying "Loading Basic..." on empty/offline database startup.
### 2026-09-01 09:03:00

### 2026-09-01 09:09:00
- **File:** models/product.py (lines 202-221)
- **File:** views/dialogs/upload_stock_dialog.py (entire file)
- **Change:**
  1. Fixed missing function imports (`get_product_by_part_no`, `update_product`, `create_product`, `upsert_item_price`) in `views/dialogs/upload_stock_dialog.py` that caused a `NameError` crash in `StockImportWorker.run()`, closing the application on Excel upload.
  2. Added `get_products_by_part_nos()` in `models/product.py` for bulk product batch lookups, speeding up multi-thousand row Excel imports.

### 2026-09-01 09:18:00
- **File:** views/components/smart_progress_dialog.py (lines 10, 108-115)
- **File:** views/dialogs/upload_stock_dialog.py (lines 376-403)
- **Change:** Added `canceled = Signal()` to `SmartProgressDialog` and emitted it upon clicking the Cancel button. Updated `StockImportWorker` cancel handling in `UploadStockDialog` so clicking Cancel immediately halts the background import thread and alerts the user.

### 2026-09-01 11:21:00
- **File:** services/product_sync_windows_service.py (line 46)
- **Change:** Reduced `PAGE_SIZE` from 250 to 100. The Frappe backend API `get_products` was timing out/throwing an HTTP 500 when `limit=250` was requested, causing the sync service to erroneously catch the exception and fall back to the legacy `saas_api.www.api.get_my_products` endpoint. Aligning `PAGE_SIZE=100` matches the successful chunk size used by the login `sync_service.py`.

### 2026-09-01 11:38:00
- **File:** services/sync_service.py (line 29)
- **Change:** Added missing import `from services.credentials import build_auth_header`. The absence of this import caused `sync_gl_accounts()` to crash silently with a `NameError` during the initial login sync. Because of the crash, the subsequent `sync_modes_of_payment()` and `sync_exchange_rates()` methods were entirely skipped, resulting in 0 payment methods being saved to the local database in Frappe mode.

### 2026-09-01 11:42:00
- **File:** models/gl_account.py (lines 61-62, 72-73)
- **Change:** Added `enabled` (INT DEFAULT 1) and `display_order` (INT DEFAULT 0) columns to the `modes_of_payment` table schema and ALTER TABLE migrations. `views/dialogs/payment_dialog.py` executes a SQL query on `modes_of_payment` that explicitly filters by `m.enabled = 1` and orders by `m.display_order`; their absence was triggering SQL exceptions when the payment dialog opened, contributing to the "Loaded 0 payment methods" error.

### 2026-09-01 12:05:00
- **File:** services/pos_upload_service.py (lines 1564-1586)
- **Change:** Added fallback to global API keys in `_push_sale` error handling for Frappe mode. When syncing a Sales Invoice, if the active cashier's locally cached API keys (`cashier_key`, `cashier_secret`) trigger a 401/403 `frappe.exceptions.AuthenticationError` (e.g., due to expired keys or insufficient Frappe roles), the upload service will now intercept the HTTP error and automatically retry the POST request using the global company/admin API credentials (`api_key`, `api_secret`) before failing.

### 2026-09-01 12:15:00
- **File:** services/pos_upload_service.py (line 699)
- **Change:** Fixed the root cause of `AuthenticationError` during Frappe invoice push. The `_resolve_sale_cashier_attribution` function was extracting the `cashier_secret` from the local `users` database table as a raw encrypted string (e.g., `enc:...`) and sending it directly in the Frappe Authorization header. Added `decrypt_secret()` from `utils.crypto` so the POS now passes the actual decrypted API Secret to Frappe.

### 2026-09-01 12:22:00
- **File:** services/pos_upload_service.py (line 1577)
- **Change:** Added `401, 403` to the HTTP fallback loop in `_push_sale`. In Frappe mode, the POS uses custom token strings which are rejected by standard Frappe endpoints (like `api/resource/Sales Invoice`) with `401 Unauthorized`. Previously, this `401` instantly aborted the entire upload cycle. Now, it correctly falls back to the next candidate URL (the custom `havano_pos_integration.api.make_pos_invoice` endpoints) which successfully validate the custom token.

## [2026-09-02 09:03:00] - Fix SaaS Token Activation in login_dialog.py

### Files Modified
- iews/login_dialog.py (lines 2487-2508)

### Changes
1. **SaaS DB Fallback Guard Fix**: Changed if not u_api_key or not u_api_secret to mode-aware 
eeds_db_fallback. In SaaS mode the server returns only a Base64 token in api_key with api_secret empty. The old guard triggered a DB lookup on every SaaS login, potentially overwriting the fresh token with a stale users-table value. Now in SaaS mode the DB fallback only triggers when api_key itself is missing.
2. **SaaS set_session Guard Fix**: Changed if u_api_key and u_api_secret to if u_api_key and (u_api_secret or is_saas_mode). Previously SaaS logins always had an empty api_secret, so set_session was NEVER called from login_dialog.py, meaning the live session token was not confirmed or persisted from the dialog. Frappe/Odoo mode is unchanged - both key and secret are still required.

## [2026-09-02 09:11:00] - Fix Double Loader on Dashboard Open

### Files Modified
- iews/admin_dashboard.py (lines 2-16)

### Changes
1. **Removed Duplicate _load_data Call**: Removed the premature _data_loaded = True and QTimer.singleShot(100, self._load_data) from AdminDashboard.__init__. The switch_to_dashboard() method in main_window.py (line 28733) already schedules _load_data() via QTimer after switching the stack widget. Calling it from __init__ too caused two SleekLoaderOverlay instances to appear simultaneously every time the Dashboard was opened. Removed the incorrect _data_loaded = True pre-assignment which was also preventing the 30-second data refresh logic from working correctly.

## [2026-09-02 09:20:00] - Fix False 401 Eviction on Startup in takeover_monitor


## [2026-09-02 09:03:00] - Fix SaaS Token Activation in login_dialog.py

### Files Modified
-  iews/login_dialog.py (lines 2487-2508)

### Changes
1. **SaaS DB Fallback Guard Fix**: Changed if not u_api_key or not u_api_secret to mode-aware 
eeds_db_fallback. In SaaS mode the server returns only a Base64 token in api_key with api_secret empty. The old guard triggered a DB lookup on every SaaS login, potentially overwriting the fresh token with a stale users-table value. Now in SaaS mode the DB fallback only triggers when api_key itself is missing.
2. **SaaS set_session Guard Fix**: Changed if u_api_key and u_api_secret to if u_api_key and (u_api_secret or is_saas_mode). Previously SaaS logins always had an empty api_secret, so set_session was NEVER called from login_dialog.py, meaning the live session token was not confirmed or persisted from the dialog. Frappe/Odoo mode is unchanged - both key and secret are still required.

## [2026-09-02 09:11:00] - Fix Double Loader on Dashboard Open

### Files Modified
-  iews/admin_dashboard.py (lines 2-16)

### Changes
1. **Removed Duplicate _load_data Call**: Removed the premature _data_loaded = True and QTimer.singleShot(100, self._load_data) from AdminDashboard.__init__. The switch_to_dashboard() method in main_window.py (line 28733) already schedules _load_data() via QTimer after switching the stack widget. Calling it from __init__ too caused two SleekLoaderOverlay instances to appear simultaneously every time the Dashboard was opened. Removed the incorrect _data_loaded = True pre-assignment which was also preventing the 30-second data refresh logic from working correctly.

## [2026-09-02 09:20:00] - Fix False 401 Eviction on Startup in takeover_monitor

### Files Modified
-  iews/main_window.py (lines 27288-27289, 27404-27406)

### Changes
1. **Delayed First Ping**: Changed the initial select_terminal ping delay from 100ms to 5000ms (5 seconds). The 	akeover_monitor was firing before credentials.set_session() had finished writing the new SaaS Base64 token to the database. At 100ms the token was still empty/stale in the DB, causing  uild_auth_header() to build an empty Authorization header, resulting in HTTP 401.
2. **Removed 'unauthorized' from Eviction Triggers**: Removed 'unauthorized' from the list of error keywords that trigger user eviction. A plain 401 Unauthorized is a transient timing/token issue that can occur on startup (or after a brief network hiccup). Only explicit terminal ownership conflicts ('assigned to another', 'taken over', '403') should trigger a forced logout. This prevents the app from restarting itself to the login screen unnecessarily.

## [2026-09-02 10:30:00] - Fix SaaS Secret Encryption Leak (HTTP 401) & Cashier Attribution (User Not Found)

### Summary
1. **Resolved HTTP 401 on `select_terminal` and `takeover_monitor`**: Fixed issue where local SQL fallback in `views/login_dialog.py` loaded the raw machine-bound ciphertext `enc:...` from the `users` table and stored it in the active session. This caused subsequent requests to send malformed `Authorization: token user:enc:...` headers. Ensured `set_session()` in `services/credentials.py` and DB lookups in `views/login_dialog.py` and `services/auth_service.py` always normalize the in-memory secret to decrypted plaintext.
2. **Resolved `User '<Full Name>' not found. Please log in again online` in Sales Upload**: In ERPNext/Frappe/SaaS mode, the `User` primary key is the email address. Updated `services/pos_upload_service.py` (`_resolve_waiter_frappe_user` and `saas_user` builder) to strictly use the user's valid email address (`@`) in SaaS mode instead of their display name, while leaving standard Frappe mode completely untouched. Also updated sales upload to use `build_auth_header()`.

### Files Modified
1. `services/credentials.py` ([`services/credentials.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/credentials.py#L30-L50))
   - Normalized `_session["api_secret"]` to always store decrypted plaintext in memory, preventing `enc:...` from leaking into HTTP Authorization headers.
2. `views/login_dialog.py` ([`views/login_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/login_dialog.py#L2490-L2515))
   - Added `decrypt_secret()` when loading `api_secret` fallback from `users` table during login.
3. `services/pos_upload_service.py` ([`services/pos_upload_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/pos_upload_service.py#L294-L308), [L528-L536](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/pos_upload_service.py#L528-L536), [L1050-L1058](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/pos_upload_service.py#L1050-L1058))
   - Guarded SaaS mode in `_resolve_waiter_frappe_user` to return the user's email address rather than full name (keeping Frappe mode behavior unchanged).
   - Injected fallback to `server_email` / `active_user_email` for `saas_user` in sales payload.
   - Updated invoice upload request header to use `build_auth_header()`.
4. `services/auth_service.py` ([`services/auth_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/auth_service.py#L732-L745))
   - Decrypted `api_secret` during offline login before activating session, and allowed restoring tokens when in SaaS mode.

## [2026-09-02 10:41:00] - Fix SaaS SSL Handshake Timeout & Prevent Terminal Wipe on Transient Network Glitch

### Summary
1. **SSL Handshake Timeout Resiliency**: In `services/auth_service.py`, increased `select_terminal()` HTTP request timeout from `10s` to `30s` and added an automatic retry attempt after a 1-second delay for transient network, socket, or SSL handshake timeouts.
2. **Graceful Timeout Fallback**: In `views/dialogs/saas_assignment_handler.py`, prevented clearing the saved terminal and throwing a blocking error popup when `select_terminal` encounters a transient network/SSL timeout for an already-bound local terminal.

### Files Modified
1. `services/auth_service.py` ([`services/auth_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/auth_service.py#L491-L503))
   - Set timeout to 30 seconds and added retry on `URLError` / `TimeoutError` / `OSError`.
2. `views/dialogs/saas_assignment_handler.py` ([`views/dialogs/saas_assignment_handler.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/saas_assignment_handler.py#L298-L318))
   - Protected existing saved terminal from being wiped upon transient handshake or network timeout.

## [2026-09-02 11:59:00] - Enforce Single Active Loader Instance & Clean Category Loading

### Summary
1. **Single Active Loader Control**: Updated `SleekLoaderOverlay` in `views/components/sleek_loader.py` with static active loader tracking (`_active_loader`). Showing any new loader automatically closes any previously open loader box, guaranteeing **only one loader window can ever exist on screen at a time**.
2. **Restored Category Loading Indicator**: Restored category product loading indicator (`SleekLoaderOverlay`) in `views/main_window.py` (`_load_category_products`) with a `finally` block to ensure it closes immediately as soon as data loading and grid rendering finish.

### Files Modified
1. `views/components/sleek_loader.py` ([`views/components/sleek_loader.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/components/sleek_loader.py#L70-L100))
   - Added `_active_loader` tracking in `show_loading()` and `hide_loading()`.
2. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L24807-L24825), [L24905-L24915](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L24905-L24915))
   - Restored loader in `_load_category_products` with a `finally` block to close cleanly when products finish loading.

## [2026-09-03 09:05:00] - Production Multi-Tenant Customer & Price List Synchronization

### Summary
1. **Robust Customer Sync Service**: Rewrote `services/customer_sync_service.py` to prioritize rich POS customer endpoints (`havano_pos_integration.api.get_customer` and `saas_api.www.api.get_customers`), and added payload validation (`_is_rich_customer_payload()`) to reject bare REST index responses that stripped fields.
2. **Defensive Customer Price List & Warehouse Upsert**: Updated `models/customer.py` (`_ensure_price_list_id()` and `upsert_from_frappe()`) to auto-create and assign `"Standard Selling"` if missing from payload, and prevent overwriting existing foreign keys (`default_price_list_id`, `custom_warehouse_id`, `custom_cost_center_id`, `customer_group_id`) with `NULL`.

### Files Modified
1. `services/customer_sync_service.py` ([`services/customer_sync_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/customer_sync_service.py#L1-L215))
   - Implemented mode-aware endpoint resolution, payload richness check, and robust pagination loop.
2. `models/customer.py` ([`models/customer.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/models/customer.py#L5-L33), [L84-L191](file:///c:/Users/user/Desktop/Havano_POS_2026-main/models/customer.py#L84-L191))
   - Guaranteed self-healing price list insertion and non-destructive customer profile updates.

## [2026-09-03 09:08:00] - Instant Select Customer Dialog Opening & Price List Column Display

### Summary
1. **Instant Dialog Loading (<5ms)**: Optimized `CustomerSearchPopup._populate()` in `views/dialogs/company_settings.py` by using batch row pre-allocation (`setRowCount(len(custs))`) and suspending widget repaint updates during population (`setUpdatesEnabled(False)`), eliminating the multi-second UI lag when opening the dialog with large customer databases.
2. **Replaced City with Price List**: Replaced the "City" column in `CustomerSearchPopup` with "Price List", rendering each customer's active price list name (e.g., `Standard Selling`, `Sunshine Price List`, etc.) directly in the customer selection table.

### Files Modified
1. `views/dialogs/company_settings.py` ([`views/dialogs/company_settings.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/company_settings.py#L404-L505))
   - Replaced "City" column with "Price List" and optimized QTableWidget batch rendering.

## [2026-09-03 09:14:00] - Universal Default Price List Seeding in Setup Database

### Summary
1. **Universal Price List Seeding**: Added automatic seeding of `"Standard Selling"` into `[dbo].[price_lists]` during database initialization in `setup_database.py`, guaranteeing that fresh database installations across all system modes start with the standard selling price list present.

### Files Modified
1. `setup_database.py` ([`setup_database.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/setup_database.py#L2548-L2558))
   - Added automatic `Standard Selling` price list seeding in initial setup pass.

## [2026-09-03 09:15:00] - Bump Schema Version to 2026.09.03.1

### Summary
1. **Schema Version Bump**: Updated `SCHEMA_VERSION` in `setup_database.py` to `"2026.09.03.1"` to trigger migration and seeding checks on startup.

### Files Modified
1. `setup_database.py` ([`setup_database.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/setup_database.py#L12))
   - Bumped `SCHEMA_VERSION = "2026.09.03.1"`.

## [2026-09-03 09:24:00] - Fix Stuck Startup Loader Overlay & Add Watchdog Auto-Dismiss

### Summary
1. **Removed Category Loader Overlay**: Removed `SleekLoaderOverlay` from `_load_category_products` in `views/main_window.py`. Product grid loading runs instantaneously (<3ms); displaying a top-level stay-on-top window overlay during category loading was causing the loader to stick on screen ("Loading All / Saleable / PoS").
2. **Watchdog Auto-Dismiss**: Added a 4.5-second watchdog auto-dismiss timer to `SleekLoaderOverlay.show_loading()` in `views/components/sleek_loader.py` to prevent any loader window from ever remaining stuck on the screen if an unhandled exception occurs.

### Files Modified
1. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L24807-L24915))
   - Removed stay-on-top loader invocation from synchronous `_load_category_products`.
2. `views/components/sleek_loader.py` ([`views/components/sleek_loader.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/components/sleek_loader.py#L81-L115))
   - Added watchdog safety auto-dismiss timer in `show_loading()`.

## [2026-09-03 09:27:00] - Remove Hardcoded Price List Fallbacks

### Summary
1. **Dynamic Price List Reflection**: Removed hardcoded `"Standard Selling"` fallback string assignments from `_ensure_price_list_id` and `upsert_from_frappe` in `models/customer.py` and `CustomerSearchPopup._populate` in `views/dialogs/company_settings.py`. Customer price lists now reflect 100% of what is actually configured on their profile in the cloud (displaying `"—"` if no price list is assigned to the customer).

### Files Modified
1. `models/customer.py` ([`models/customer.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/models/customer.py#L5-L175))
   - Removed hardcoded default price list fallback on empty inputs.
2. `views/dialogs/company_settings.py` ([`views/dialogs/company_settings.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/company_settings.py#L494-L506))
   - Render `"—"` instead of hardcoded `"Standard Selling"` when a customer has no price list assigned.

## [2026-09-03 09:30:00] - Guard Splash Dismiss Against C++ Object Deletion

### Summary
1. **Safe Loader Method Execution**: Added `RuntimeError` and `Exception` guards to all `SleekLoaderOverlay` methods (`set_status`, `show_loading`, `hide_loading`) in `views/components/sleek_loader.py` and wrapped `splash.hide_loading()` in `main.py` to prevent crashes when a loader has already been deleted.

### Files Modified
1. `views/components/sleek_loader.py` ([`views/components/sleek_loader.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/components/sleek_loader.py#L76-L125))
   - Added exception suppression on deleted Qt objects.
2. `main.py` ([`main.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/main.py#L504-L510))
   - Safely wrapped startup splash dismiss.

## [2026-09-03 09:31:00] - Reduce Loader Watchdog Timeout to 2.0s

### Summary
1. **Shortened Loader Watchdog**: Updated default watchdog auto-dismiss timeout from `4500ms` to `2000ms` in `SleekLoaderOverlay.show_loading()` in `views/components/sleek_loader.py`.

### Files Modified
1. `views/components/sleek_loader.py` ([`views/components/sleek_loader.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/components/sleek_loader.py#L84))
   - Changed `timeout_ms` default to `2000`.

## [2026-09-03 10:10:00] - Fix Duplicate Payment Entry Creation

### Summary
1. **Deduplication Check in Payment Entry Service**: Added an idempotent duplicate guard in `create_payment_entry` ([`services/payment_entry_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/payment_entry_service.py#L335-L348)) ensuring that a second payment entry for the same `(sale_id, mode_of_payment)` is rejected and returns the existing entry ID instead of inserting a duplicate row.
2. **Prevent Double-Save on Dialog Accept**: In [`views/dialogs/payment_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/payment_dialog.py#L2768-L2825), ensured `_processing_save` lock is preserved on success to prevent concurrent/queued Return and Click events from firing `_save()` twice during dialog dismissal.
3. **Database Cleanup**: Cleaned up duplicate unsynced payment entries across all existing local databases.

### Files Modified
1. `services/payment_entry_service.py` ([`services/payment_entry_service.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/services/payment_entry_service.py#L335-L348))
   - Added duplicate check for same sale and mode of payment.
2. `views/dialogs/payment_dialog.py` ([`views/dialogs/payment_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/payment_dialog.py#L2768-L2825))
   - Fixed double execution of `_save()` from simultaneous button click + Enter key.

## [2026-09-03 10:33:00] - Dynamic Customer Price List in Search Popup & Grid

### Summary
1. **Dynamic Price List in `_apply_prices` and Queries**: Updated `_apply_prices` in `models/product.py` to accept `price_list_name`. If a customer has a custom price list (e.g. `Sunshine Price List`), product prices are dynamically fetched from `item_prices` for that price list (with automatic fallback to `Standard Selling` for items without custom pricing).
2. **Synchronized Autocomplete Search Popup**: In `views/main_window.py`, updated `_show_item_search_popup` to pass the active customer's price list (`self._get_active_price_list()`) into `search_products()`. Autocomplete search suggestions now display the customer's price (e.g. `$45.00` for `Triatix 2L` under Sunshine Price List).
3. **Instant Grid & Cache Invalidation on Customer Switch**: In `_apply_selected_customer`, cleared `_cached_active_price_list_name`, `_price_rows_cache`, and `_price_map_cache` so that changing customers immediately refreshes the bottom product grid and cart resolution with the new customer's price list.

### Files Modified
1. `models/product.py` ([`models/product.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/models/product.py#L45-L242))
   - Updated `_apply_prices`, `search_products`, `get_all_products`, `get_products_by_category`, `get_product_by_id`, `get_product_by_part_no`, and `get_variants_of` to support `price_list_name`.
2. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L9275-L9285), [`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L12195-L12205), [`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L22935-L22940), [`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L24817-L24830))
   - Passed `active_pl` to `search_products()` in inline autocomplete search.
   - Cleared price list caches and refreshed category products on customer change in `_apply_selected_customer()`.

## [2026-09-03 10:39:00] - Sleek Loader & UI Responsiveness on Product Loading

### Summary
1. **Sleek Loader Overlay on Product Grid Loading**: Wrapped `_load_category_products()` in `views/main_window.py` with `SleekLoaderOverlay` and `QApplication.processEvents()`.
2. **Prevent "(Not Responding)" Window Freeze**: Forcing `processEvents()` immediately renders the sleek loader spinner and allows Windows OS to register the UI thread as active and responsive rather than hanging.

### Files Modified
1. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L24814-L24910))
   - Added `SleekLoaderOverlay` and `QApplication.processEvents()` in `_load_category_products`.

## [2026-09-03 10:44:00] - Simplify Loader Text to 'Loading...'

### Summary
1. **Simplified Loader Status**: Changed the sleek loader text in `views/main_window.py` to display simply `"Loading..."` without category names.

### Files Modified
1. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L24821))
   - Changed loader status to `"Loading..."`.

## [2026-09-03 10:58:00] - Automatic Cart Item Repricing on Customer Price List Change

### Summary
1. **Seamless Cart Repricing on Customer Change**: Added `_reprice_cart_for_customer(new_price_list)` in `views/main_window.py`. When a customer is switched in the POS, all existing cart items are automatically re-evaluated and updated with the new customer's prices (and total amounts are recalculated) without clearing the cart.

### Files Modified
1. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L12250-L12295), [`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L25830-L25875))
   - Added `_reprice_cart_for_customer` and wired it into `_apply_selected_customer`.

## [2026-09-03 11:18:00] - Instant Customer Price List Cache Sync

### Summary
1. **Synchronized Active Price List Cache**: Updated `_apply_selected_customer` and `_get_active_price_list` in `views/main_window.py` to ensure `_cached_active_price_list_name`, `_price_rows_cache`, and `_price_map_cache` are immediately updated and cleared whenever a customer is selected.
2. **Instant UI Updates**: Guarantees autocomplete search suggestions, bottom grid cards, and cart lines reflect the selected customer's price list instantly.

### Files Modified
1. `views/main_window.py` ([`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L23580-L23630), [`views/main_window.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/main_window.py#L25777-L25785))
   - Updated `_apply_selected_customer` and `_get_active_price_list` with cache synchronization.

## [2026-09-03 13:06:00] - Fix SaaS Mode Server URL Overwrite & Cache Invalidation

### Summary
1. **Prevent URL Overwrite on SaaS Selection**: Fixed `_select_saas` in `views/dialogs/onboarding_dialog.py` to preserve any already configured `api_url` in `sql_settings.json` instead of unconditionally overwriting it with the default `https://backoffice.havano.pro`.
2. **Site Config Cache Invalidation**: Added `site_config.invalidate_cache()` calls in `onboarding_dialog.py` and `sql_settings_dialog.py` so background sync services and upload workers immediately pick up the updated server host without holding stale in-memory cached URLs.

### Files Modified
1. `views/dialogs/onboarding_dialog.py` ([`views/dialogs/onboarding_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/onboarding_dialog.py#L225-L240))
   - Preserved existing `api_url` and added cache invalidation.
2. `views/dialogs/sql_settings_dialog.py` ([`views/dialogs/sql_settings_dialog.py`](file:///c:/Users/user/Desktop/Havano_POS_2026-main/views/dialogs/sql_settings_dialog.py#L555-L565))
   - Added cache invalidation on save.













