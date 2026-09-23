from views.components.odoo_module import OdooModuleView
from PySide6.QtWidgets import QMessageBox, QWidget


def not_implemented(dashboard, name):
    return lambda: dashboard._coming_soon(name)


def open_item_sales(dashboard):
    from views.reports.bi_reports import ItemSalesReportDialog
    ItemSalesReportDialog(dashboard.parent_window).exec()


def open_category_sales(dashboard):
    from views.reports.bi_reports import CategorySalesReportDialog
    CategorySalesReportDialog(dashboard.parent_window).exec()


def open_item_profit(dashboard):
    from views.reports.bi_reports import ItemProfitabilityReportDialog
    ItemProfitabilityReportDialog(dashboard.parent_window).exec()


def open_category_profit(dashboard):
    from views.reports.bi_reports import CategoryProfitabilityReportDialog
    CategoryProfitabilityReportDialog(dashboard.parent_window).exec()


def open_cashier_sales(dashboard):
    from views.reports.bi_reports import CashierSalesReportDialog
    CashierSalesReportDialog(dashboard.parent_window).exec()


def open_till_profit(dashboard):
    from views.reports.bi_reports import TillProfitabilityReportDialog
    TillProfitabilityReportDialog(dashboard.parent_window).exec()


def open_daily_avg_profit(dashboard):
    from views.reports.bi_reports import DailyAverageProfitReportDialog
    DailyAverageProfitReportDialog(dashboard.parent_window).exec()


def open_management_report(dashboard):
    from views.reports.bi_reports import ManagementReportDialog
    ManagementReportDialog(dashboard.parent_window).exec()


def _run_pos_action(dashboard, action_name, fallback_title):
    pos = getattr(dashboard.parent_window, "_pos_view", None)
    if pos and hasattr(pos, action_name):
        getattr(pos, action_name)()
    elif hasattr(dashboard.parent_window, action_name):
        getattr(dashboard.parent_window, action_name)()
    else:
        not_implemented(dashboard, fallback_title)()


# =========================================================================
# 1. SALES MODULE BUILDER
# =========================================================================
def build_sales_module(dashboard):
    sales = OdooModuleView("Sales", dashboard)
    sales.on_back_requested(lambda: dashboard.stack.setCurrentIndex(0))
    sales.add_tab_direct("Dashboard", lambda: dashboard._build_overview_tab())
    sales.add_tab_dropdown("Master")
    sales.add_tab_dropdown("Operations")
    sales.add_tab_dropdown("Reporting")
    sales.add_tab_dropdown("Configurations")

    def open_quotations():
        from views.dialogs.quotation_dialog import QuotationDialog
        QuotationDialog(dashboard.parent_window, user=getattr(dashboard.parent_window, "user", None)).exec()

    def open_credit_notes_dialog():
        from views.dialogs.credit_notes_list_dialog import CreditNotesListDialog
        dlg = CreditNotesListDialog(dashboard.parent_window)
        from PySide6.QtCore import Qt
        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.show()

    sales.add_dropdown_action("Operations", "POS", lambda: _run_pos_action(dashboard, "switch_to_pos", "POS"))
    sales.add_dropdown_action("Operations", "Quotations", open_quotations)
    sales.add_dropdown_action("Operations", "Credit Notes", open_credit_notes_dialog)
    sales.add_dropdown_action("Operations", "Sales Order", lambda: _run_pos_action(dashboard, "_open_sales_order_list", "Sales Order"))
    
    def _create_shift_recon():
        from views.inventory.shift_reconciliation_screen import ShiftReconciliationScreen
        return ShiftReconciliationScreen(dashboard.parent_window)
    sales.add_dropdown_screen("Operations", "Shift Reconciliation", _create_shift_recon)
    
    sales.add_dropdown_action("Operations", "Sales Invoice List", lambda: _run_pos_action(dashboard, "_open_sales_list", "Sales Invoices"))
    sales.add_dropdown_action("Operations", "Sales Report", lambda: _run_pos_action(dashboard, "_open_sales_report_tab", "Sales Report"))
    sales.add_dropdown_action("Operations", "Payments", lambda: _run_pos_action(dashboard, "_open_customer_payment_entry", "Payments"))
    sales.add_dropdown_action("Operations", "Reprint Shift Reconciliation", lambda: _run_pos_action(dashboard, "_open_shift_reprint", "Reprint Shift Reconciliation"))

    def open_customers():
        from views.dialogs.settings_dialog import CustomerDialog
        from PySide6.QtCore import Qt
        dlg = CustomerDialog(dashboard.parent_window)
        dlg.setWindowState(Qt.WindowMaximized)
        dlg.exec()

    sales.add_dropdown_action("Master", "Customers", open_customers)
    sales.add_dropdown_action("Master", "Customer Groups", dashboard._sd_action("CustomerGroupDialog"))
    sales.add_dropdown_action("Master", "Price Lists", dashboard._sd_action("PriceListDialog"))

    sales.add_dropdown_screen("Reporting", "Shift List", lambda: dashboard._build_shift_history_tab())
    sales.add_dropdown_action("Reporting", "Sales Invoices", lambda: _run_pos_action(dashboard, "_open_sales_list", "Sales Invoices"))
    sales.add_dropdown_action("Reporting", "Sales Orders", lambda: _run_pos_action(dashboard, "_open_sales_order_list", "Sales Orders"))
    sales.add_dropdown_action("Reporting", "Sales Report", lambda: _run_pos_action(dashboard, "_open_sales_report_tab", "Sales Report"))

    def _create_consumed_items():
        from views.reports.consumed_items_report_page import ConsumedItemsReportPage
        return ConsumedItemsReportPage(dashboard.parent_window)
    sales.add_dropdown_screen("Reporting", "Consumed Items Report", _create_consumed_items)

    sales.add_dropdown_action("Reporting", "Item Sales", lambda: open_item_sales(dashboard))
    sales.add_dropdown_action("Reporting", "Category Sales", lambda: open_category_sales(dashboard))
    sales.add_dropdown_action("Reporting", "Item Profitability", lambda: open_item_profit(dashboard))
    sales.add_dropdown_action("Reporting", "Category Profitability", lambda: open_category_profit(dashboard))
    sales.add_dropdown_action("Reporting", "Cashier Sales", lambda: open_cashier_sales(dashboard))
    sales.add_dropdown_action("Reporting", "Till Profitability", lambda: open_till_profit(dashboard))
    sales.add_dropdown_action("Reporting", "Daily Avg Profit / Inv", lambda: open_daily_avg_profit(dashboard))

    sales.add_dropdown_action("Reporting", "Credit Notes", open_credit_notes_dialog)
    sales.add_dropdown_screen("Reporting", "Recent Sales", lambda: dashboard._build_recent_sales_page())
    sales.add_dropdown_action("Reporting", "Quotation", lambda: _run_pos_action(dashboard, "_open_quotation_manager", "Quotation Report"))

    def open_payment_methods():
        from views.dialogs.payment_modes_dialog import PaymentModesDialog
        PaymentModesDialog(dashboard.parent_window).exec()

    sales.add_dropdown_action("Configurations", "Payment Methods", open_payment_methods)
    sales.add_dropdown_action("Configurations", "Category Visibility", lambda: dashboard._open_cat_dialog())

    return sales


# =========================================================================
# 2. SUPPLIERS MODULE BUILDER
# =========================================================================
def build_suppliers_module(dashboard):
    suppliers = OdooModuleView("Suppliers", dashboard)
    suppliers.on_back_requested(lambda: dashboard.stack.setCurrentIndex(0))

    def _create_supplier_dashboard():
        from views.reports.supplier_dashboard import SupplierDashboardWidget
        return SupplierDashboardWidget(dashboard.parent_window)
    suppliers.add_tab_direct("Dashboard", _create_supplier_dashboard)

    suppliers.add_tab_dropdown("Master")
    suppliers.add_tab_dropdown("Operations")
    suppliers.add_tab_dropdown("Reporting")

    def open_supplier_dlg():
        from views.dialogs.supplier_dialog import SupplierDialog
        SupplierDialog(dashboard.parent_window).exec()

    suppliers.add_dropdown_action("Master", "Supplier", open_supplier_dlg)

    def open_purchase_invoice_dlg():
        from views.dialogs.purchase_invoices_list_dialog import PurchaseInvoicesListDialog
        PurchaseInvoicesListDialog(dashboard.parent_window).exec()

    def open_purchase_invoice_reports():
        from views.dialogs.purchase_invoices_list_dialog import PurchaseInvoicesListDialog
        dlg = PurchaseInvoicesListDialog(dashboard.parent_window)
        if hasattr(dlg, "_add_btn") and dlg._add_btn:
            dlg._add_btn.hide()
        dlg.exec()

    def open_purchase_return_dlg():
        from views.dialogs.purchase_invoices_list_dialog import PurchaseInvoicesListDialog
        PurchaseInvoicesListDialog(dashboard.parent_window, is_return=True).exec()

    suppliers.add_dropdown_action("Operations", "Purchase Invoices", open_purchase_invoice_dlg)
    suppliers.add_dropdown_action("Operations", "Purchase Returns", open_purchase_return_dlg)

    def _create_supplier_payment():
        from views.dialogs.supplier_payment_dialog import ProcessSupplierPaymentDialog
        return ProcessSupplierPaymentDialog(dashboard.parent_window)
    suppliers.add_dropdown_screen("Operations", "Process Supplier Payment", _create_supplier_payment)
    suppliers.add_dropdown_action("Reporting", "Purchase Invoices", open_purchase_invoice_reports)

    def _create_supplier_list_report():
        from views.reports.supplier_list_report import SupplierListReport
        return SupplierListReport(dashboard.parent_window)
    suppliers.add_dropdown_screen("Reporting", "Supplier List", _create_supplier_list_report)

    return suppliers


# =========================================================================
# 3. FINANCE MODULE BUILDER
# =========================================================================
def build_finance_module(dashboard):
    finance = OdooModuleView("Finance", dashboard)
    finance.on_back_requested(lambda: dashboard.stack.setCurrentIndex(0))
    finance.add_tab_direct("Dashboard", lambda: dashboard._build_finance_dashboard())
    finance.add_tab_dropdown("Master")
    finance.add_tab_dropdown("Operations")
    finance.add_tab_dropdown("Reporting")
    finance.add_tab_dropdown("Configurations")

    def open_payment_methods():
        from views.dialogs.payment_modes_dialog import PaymentModesDialog
        PaymentModesDialog(dashboard.parent_window).exec()

    def open_finance_expense():
        from views.dialogs.expense_dialog import ProcessExpenseDialog
        ProcessExpenseDialog(dashboard.parent_window).exec()

    finance.add_dropdown_action("Master", "Expenses", open_finance_expense)
    finance.add_dropdown_action("Master", "Payment Methods", open_payment_methods)

    def _create_pnl():
        from views.reports.profit_and_loss_report import ProfitAndLossReport
        return ProfitAndLossReport(dashboard.parent_window)
    finance.add_dropdown_screen("Reporting", "Profit & Loss Reports", _create_pnl)

    def _create_expense_report():
        from views.reports.expense_list_report import ExpenseListReport
        return ExpenseListReport(dashboard.parent_window)
    finance.add_dropdown_screen("Reporting", "Expenses", _create_expense_report)

    def _create_cash_day_book():
        from views.reports.cash_day_book_report import CashDayBookReport
        return CashDayBookReport(dashboard.parent_window)
    finance.add_dropdown_screen("Reporting", "Cash Day Book", _create_cash_day_book)

    def _create_cash_ledger():
        from views.reports.cash_ledger_report import CashLedgerReport
        return CashLedgerReport(dashboard.parent_window)
    finance.add_dropdown_screen("Reporting", "Cash Ledger Report", _create_cash_ledger)

    def _create_payment_breakdown():
        from views.reports.invoice_payment_breakdown_report import InvoicePaymentBreakdownReport
        return InvoicePaymentBreakdownReport(dashboard.parent_window)
    finance.add_dropdown_screen("Reporting", "Invoice Payment Breakdown", _create_payment_breakdown)

    def _create_mgmt_report():
        from views.reports.management_report import ManagementReportPage
        return ManagementReportPage(dashboard.parent_window)
    finance.add_dropdown_screen("Reporting", "Management Report", _create_mgmt_report)

    finance.add_dropdown_action("Reporting", "Sales: Item Sales", lambda: open_item_sales(dashboard))
    finance.add_dropdown_action("Reporting", "Sales: Category Sales", lambda: open_category_sales(dashboard))
    finance.add_dropdown_action("Reporting", "Sales: Item Profitability", lambda: open_item_profit(dashboard))
    finance.add_dropdown_action("Reporting", "Sales: Category Profitability", lambda: open_category_profit(dashboard))
    finance.add_dropdown_action("Reporting", "Sales: Cashier Sales", lambda: open_cashier_sales(dashboard))
    finance.add_dropdown_action("Reporting", "Sales: Till Profitability", lambda: open_till_profit(dashboard))
    finance.add_dropdown_action("Reporting", "Management Report", lambda: open_management_report(dashboard))

    def _create_supplier_payment_fin():
        from views.dialogs.supplier_payment_dialog import ProcessSupplierPaymentDialog
        return ProcessSupplierPaymentDialog(dashboard.parent_window)
    finance.add_dropdown_screen("Operations", "Process Supplier Payment", _create_supplier_payment_fin)

    def open_exchange_rates():
        from views.dialogs.exchange_rate_dialog import ExchangeRateDialog
        ExchangeRateDialog(dashboard.parent_window).exec()

    finance.add_dropdown_action("Configurations", "Exchange rates", open_exchange_rates)
    finance.add_dropdown_action("Configurations", "Payment Methods", open_payment_methods)
    finance.add_dropdown_action("Configurations", "Cost Center", dashboard._sd_action("CostCenterDialog"))

    def open_tax_settings():
        from views.dialogs.tax_rules_dialog import TaxRulesDialog
        TaxRulesDialog(dashboard.parent_window).exec()

    finance.add_dropdown_action("Configurations", "Tax Settings", open_tax_settings)

    return finance


# =========================================================================
# 4. INVENTORY MODULE BUILDER
# =========================================================================
def build_inventory_module(dashboard):
    inventory = OdooModuleView("Inventory", dashboard)
    inventory.on_back_requested(lambda: dashboard.stack.setCurrentIndex(0))
    inventory.add_tab_direct("Dashboard", lambda: dashboard._build_inventory_dashboard())
    inventory.add_tab_dropdown("Master")
    inventory.add_tab_dropdown("Operations")
    inventory.add_tab_dropdown("Reporting")
    inventory.add_tab_dropdown("Configurations")

    stock_tab_idx = inventory.stack.count()
    inventory.stack.addWidget(dashboard._build_stock_tab())

    def _create_stock_recon():
        from views.inventory.stock_reconciliation_screen import StockReconciliationScreen
        return StockReconciliationScreen(dashboard.parent_window)
    inventory.add_dropdown_screen("Operations", "Stock Take", _create_stock_recon)

    def _create_stock_adjustments():
        from views.inventory.stock_adjustments_screen import StockAdjustmentsScreen
        return StockAdjustmentsScreen(dashboard.parent_window)
    inventory.add_dropdown_screen("Operations", "Stock Adjustments", _create_stock_adjustments)

    def open_bundle_dialog():
        from views.dialogs.bundle_dialog import BundleDialog
        BundleDialog(dashboard.parent_window).exec()

    inventory.add_dropdown_action("Operations", "Add Product Bundle", open_bundle_dialog)

    def _create_stock_transfer():
        from views.inventory.stock_transfer_screen import StockTransferScreen
        return StockTransferScreen(dashboard.parent_window)
    inventory.add_dropdown_screen("Operations", "Stock Transfer", _create_stock_transfer)

    inventory.add_dropdown_action("Master", "Products", lambda: (
        inventory.stack.setCurrentIndex(stock_tab_idx),
        dashboard._add_stock_btn.setVisible(True) if hasattr(dashboard, "_add_stock_btn") else None,
        dashboard._load_stock_data()
    ))

    def open_item_group():
        from views.dialogs.item_group_dialog import ItemGroupDialog
        ItemGroupDialog(dashboard.parent_window).exec()

    inventory.add_dropdown_action("Master", "Category", open_item_group)

    def open_low_stock():
        from views.reports.bi_reports import LowStockReportDialog
        LowStockReportDialog(dashboard.parent_window).exec()

    def open_expired_goods():
        from views.reports.bi_reports import ExpiredGoodsReportDialog
        ExpiredGoodsReportDialog(dashboard.parent_window).exec()

    def open_batch_stock():
        from views.reports.bi_reports import BatchStockReportDialog
        BatchStockReportDialog(dashboard.parent_window).exec()

    def open_hist_val():
        from views.reports.bi_reports import HistoricalValuationReportDialog
        HistoricalValuationReportDialog(dashboard.parent_window).exec()

    def open_breakages_report():
        from views.reports.bi_reports import StockAdjustmentReportDialog
        StockAdjustmentReportDialog(dashboard.parent_window, reason="Breakages", title="Breakages Report").exec()

    def open_wastages_report():
        from views.reports.bi_reports import StockAdjustmentReportDialog
        StockAdjustmentReportDialog(dashboard.parent_window, reason="Wastages", title="Wastages Report").exec()

    def open_adjustments_report():
        from views.reports.bi_reports import StockAdjustmentReportDialog
        StockAdjustmentReportDialog(dashboard.parent_window, reason="Adjustments", title="Adjustments Report").exec()

    inventory.add_dropdown_action("Reporting", "Stock Valuation", open_hist_val)

    def _create_detailed_ledger():
        from views.reports.detailed_inventory_ledger import DetailedInventoryLedger
        return DetailedInventoryLedger(dashboard.parent_window)
    inventory.add_dropdown_screen("Reporting", "Detailed Inventory Ledger", _create_detailed_ledger)

    def _create_summary_ledger():
        from views.reports.summary_inventory_ledger import SummaryInventoryLedger
        return SummaryInventoryLedger(dashboard.parent_window)
    inventory.add_dropdown_screen("Reporting", "Summary Inventory Ledger", _create_summary_ledger)

    inventory.add_dropdown_action("Reporting", "Breakages Report", open_breakages_report)
    inventory.add_dropdown_action("Reporting", "Wastages Report", open_wastages_report)
    inventory.add_dropdown_action("Reporting", "Low Stock Report", open_low_stock)
    inventory.add_dropdown_action("Reporting", "Expired Goods", open_expired_goods)
    inventory.add_dropdown_action("Reporting", "Batch Stock Report", open_batch_stock)
    inventory.add_dropdown_action("Reporting", "Adjustment Report", open_adjustments_report)

    def _create_disabled_items():
        from views.reports.disabled_items_report import DisabledItemsReport
        return DisabledItemsReport(dashboard.parent_window)
    inventory.add_dropdown_screen("Reporting", "Disabled Items Reports", _create_disabled_items)

    def open_uom():
        from views.dialogs.uom_dialog import UOMDialog
        UOMDialog(dashboard.parent_window).exec()

    def open_dosages():
        try:
            from views.dialogs.pharmacy_masters_dialog import PharmacyMastersDialog
            dlg = PharmacyMastersDialog(dashboard.parent_window)
            if hasattr(dlg, '_tabs'):
                dlg._tabs.setCurrentIndex(1)
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(dashboard.parent_window, "Error", f"Could not open Dosages:\n{e}")

    inventory.add_dropdown_action("Configurations", "Warehouses", dashboard._sd_action("WarehouseDialog"))
    inventory.add_dropdown_action("Configurations", "UOM", open_uom)

    def _create_batches_screen():
        from views.inventory.batches_screen import BatchesScreen
        return BatchesScreen(dashboard.parent_window)
    inventory.add_dropdown_screen("Configurations", "Batches", _create_batches_screen)

    try:
        from settings.pharmacy_settings import get_pharmacy_mode
        pharmacy_mode_enabled = bool(get_pharmacy_mode())
    except Exception:
        pharmacy_mode_enabled = False

    if pharmacy_mode_enabled:
        inventory.add_dropdown_action("Configurations", "Dosages", open_dosages)

    inventory.add_dropdown_action("Configurations", "Variants", not_implemented(dashboard, "Variants"))

    def _create_costing_method():
        from views.pages.costing_method_page import CostingMethodPage
        return CostingMethodPage(dashboard.parent_window)
    inventory.add_dropdown_screen("Configurations", "Cost Method", _create_costing_method)

    return inventory


# =========================================================================
# 5. EXPENSES MODULE BUILDER
# =========================================================================
def build_expenses_module(dashboard):
    from views.reports.expense_list_report import ExpenseListReport
    expenses = OdooModuleView("Expenses", dashboard)
    expenses.on_back_requested(lambda: dashboard.stack.setCurrentIndex(0))
    expenses.add_tab_direct("Expenses", ExpenseListReport(dashboard.parent_window, on_back=lambda: dashboard.stack.setCurrentIndex(0)))

    def open_process_expense():
        from views.dialogs.expense_dialog import ProcessExpenseDialog
        ProcessExpenseDialog(dashboard.parent_window).exec()

    expenses.add_tab_dropdown("Master")
    expenses.add_dropdown_action("Master", "Expenses", open_process_expense)

    expenses.add_tab_dropdown("Operations")
    expenses.add_dropdown_screen("Operations", "Shift History", lambda: dashboard._build_shift_history_tab())
    expenses.add_dropdown_action("Operations", "Process Expense", open_process_expense)

    expenses.add_tab_dropdown("Reporting")
    expenses.add_dropdown_screen("Reporting", "Expenses", lambda: ExpenseListReport(dashboard.parent_window))

    expenses.add_tab_dropdown("Configurations")
    return expenses


# =========================================================================
# 6. SETTINGS MODULE BUILDER (FAST & LAZY)
# =========================================================================
def build_settings_module(dashboard):
    settings = OdooModuleView("Settings", dashboard)
    settings.on_back_requested(lambda: dashboard.stack.setCurrentIndex(0))
    settings.add_tab_direct("Dashboard", dashboard._build_settings_dashboard())
    settings.add_tab_dropdown("Configurations")

    def open_adv_settings():
        from views.dialogs.advance_settings_dialog import AdvanceSettingsDialog
        AdvanceSettingsDialog(dashboard.parent_window).exec()

    def open_scale_settings():
        from views.main_window import BarcodeSettingsDialog
        BarcodeSettingsDialog(dashboard.parent_window).exec()

    settings.add_dropdown_action("Configurations", "Companies", dashboard._sd_action("CompanyDialog"))
    settings.add_dropdown_action("Configurations", "POS Rules", dashboard._sd_action("POSRulesDialog"))
    settings.add_dropdown_action("Configurations", "Scale Settings", open_scale_settings)
    settings.add_dropdown_action("Configurations", "Advanced Settings", open_adv_settings)
    settings.add_dropdown_action("Configurations", "Maintenance Settings", lambda: dashboard._open_maint_dialog())
    settings.add_dropdown_action("Configurations", "Printing", dashboard._sd_action("HardwareDialog"))
    settings.add_dropdown_action("Configurations", "Users", dashboard._sd_action("ManageUsersDialog"))

    # Lazy load BackupSettingsView so clicking Settings doesn't block on directory scans
    def _create_backup_view():
        from views.dialogs.backup_settings_dialog import BackupSettingsView
        return BackupSettingsView(dashboard.parent_window)
    settings.add_dropdown_screen("Configurations", "Backup & Restore", _create_backup_view)

    # Lazy load UpdateSettingsView so clicking Settings doesn't block on network version checks
    def _create_update_view():
        from views.dialogs.update_settings_dialog import UpdateSettingsView
        return UpdateSettingsView(dashboard.parent_window)
    settings.add_dropdown_screen("Configurations", "Updates", _create_update_view)

    def open_license_dialog():
        from views.dialogs.license_dialog import LicenseDialog
        LicenseDialog(dashboard.parent_window).exec()

    def open_help_link():
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl("https://www.havanoerp.com/"))

    settings.add_dropdown_action("Configurations", "License Details", open_license_dialog)
    settings.add_dropdown_action("Configurations", "Help", open_help_link)

    return settings


# =========================================================================
# UNIFIED MODULE DISPATCHER
# =========================================================================
MODULE_BUILDERS = {
    "Sales": build_sales_module,
    "Suppliers": build_suppliers_module,
    "Finance": build_finance_module,
    "Inventory": build_inventory_module,
    "Expenses": build_expenses_module,
    "Settings": build_settings_module,
}


def build_odoo_module(dashboard, name: str) -> QWidget:
    """Build a single Odoo module on-demand to keep module navigation 0ms instant."""
    builder = MODULE_BUILDERS.get(name)
    if builder:
        return builder(dashboard)
    return QWidget()


def build_odoo_modules(dashboard):
    """
    Backward-compatible lazy dictionary that instantiates modules only when accessed.
    Eliminates the 15-30s freeze caused by eagerly constructing all modules at once.
    """
    class _LazyModulesDict(dict):
        def __init__(self, dash):
            super().__init__()
            self._dash = dash

        def __getitem__(self, key):
            if not super().__contains__(key):
                self[key] = build_odoo_module(self._dash, key)
            return super().__getitem__(key)

        def get(self, key, default=None):
            if not super().__contains__(key):
                if key in MODULE_BUILDERS:
                    val = build_odoo_module(self._dash, key)
                    if val is not None:
                        self[key] = val
                        return val
                return default
            return super().get(key, default)

        def __contains__(self, key):
            return key in MODULE_BUILDERS or super().__contains__(key)

    return _LazyModulesDict(dashboard)
