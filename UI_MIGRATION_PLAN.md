# Havano POS: UI Standardization & Migration Plan

## Objective
Transform every list-view and reporting module across Havano POS to inherit from the centralized `ReportTemplate`. This ensures:
1. **Unified Aesthetics**: A consistent, modern Havano theme with stripped "List/Report" titles.
2. **Centralized Functionality**: Native Search, PDF Export, Excel Export, and Date Filtering without redundant code in each file.
3. **Simplified Maintenance**: A single source of truth (`report_template.py`) for all table and filter layouts.

## Phase 1: Completed Migrations
The following core Sales modules have been successfully refactored:
- [x] **Sales Orders** (`sales_order_list_dialog.py`) - Natively uses ReportTemplate
- [x] **Quotations** (`quotation_dialog.py`) - Master-Detail view with ReportTemplate powering the left pane list.
- [x] **Credit Notes** (`credit_notes_list_dialog.py`) - Completely rewritten to use ReportTemplate natively.
- [x] **Sales Invoices** (`sales_list_dialog.py`) - Renamed and standardized toolbar to "Sales Invoices".
- [x] **Purchase Invoices** (`purchase_invoices_list_dialog.py`) - Wrapped in ReportTemplate.
- [x] **Consumed Items Report** (`consumed_items_report_page.py`) - Disconnected default filters, pulls direct DB data into ReportTemplate.

## Phase 2: In-Progress / Remaining Reports
The following reports need the `ReportTemplate` implementation:
- [x] **Daily Average Profit Report** (`daily_profit_report.py`)
- [x] **Shift Report (X-Report)** & **POS Reports Center** (`pos_reports.py`)
- [x] **Inventory List Dialog** (`inventory_list_dialog.py`)
- [x] **Expense List Report** (`expense_list_report.py`)
- [x] **Supplier List Report** (`supplier_list_report.py`)
- [x] **Stock Valuation Report** (`bi_reports.py` - HistoricalValuationReportDialog)
- [x] **Inventory Ledger (Detailed & Summary)** (`detailed_inventory_ledger.py` & `summary_inventory_ledger.py`)
- [ ] **Cash Day Book Report** (Excluded, non-listview style per user request)
- [ ] **Cash Ledger Report** (Excluded, non-listview style per user request)
- [ ] **Profit and Loss Report** (Excluded, non-listview style per user request)
- [ ] **Management Report** (Excluded, non-listview style per user request)

## Phase 3: Testing & Final Review
- Verify that PDF/Excel buttons map to native actions across all migrated screens.
- Ensure no lingering "List" or "Report" words in screen top headers.
- Confirm row interactions (e.g., Double click to view details) still work identically using `self.report.table.itemSelectionChanged` and `self.report.table.doubleClicked`.
