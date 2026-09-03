from views.components.odoo_module import OdooModuleView
from PySide6.QtWidgets import QMessageBox

def build_odoo_modules(dashboard):
    """
    Builds and returns a dictionary of all the Odoo-style modules.
    dashboard: The AdminDashboard instance, used to access parent_window methods.
    """
    modules = {}

    def not_implemented(name):
        return lambda: dashboard._coming_soon(name)

    def open_item_sales():
        from views.reports.bi_reports import ItemSalesReportDialog
        ItemSalesReportDialog(dashboard.parent_window).exec()

    def open_category_sales():
        from views.reports.bi_reports import CategorySalesReportDialog
        CategorySalesReportDialog(dashboard.parent_window).exec()

    def open_item_profit():
        from views.reports.bi_reports import ItemProfitabilityReportDialog
        ItemProfitabilityReportDialog(dashboard.parent_window).exec()

    def open_category_profit():
        from views.reports.bi_reports import CategoryProfitabilityReportDialog
        CategoryProfitabilityReportDialog(dashboard.parent_window).exec()

    def open_cashier_sales():
        from views.reports.bi_reports import CashierSalesReportDialog
        CashierSalesReportDialog(dashboard.parent_window).exec()

    def open_till_profit():
        from views.reports.bi_reports import TillProfitabilityReportDialog
        TillProfitabilityReportDialog(dashboard.parent_window).exec()

    def open_daily_avg_profit():
        from views.reports.bi_reports import DailyAverageProfitReportDialog
        DailyAverageProfitReportDialog(dashboard.parent_window).exec()

    def open_management_report():
        from views.reports.bi_reports import ManagementReportDialog
        ManagementReportDialog(dashboard.parent_window).exec()

    # 1. SALES
    sales = OdooModuleView("Sales", dashboard)
    sales.on_back_requested(lambda: dashboard.stack.setCurrentIndex(0))
    sales.add_tab_direct("Dashboard", dashboard._build_overview_tab())
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

    def _run_pos_action(action_name, fallback_title):
        pos = getattr(dashboard.parent_window, "_pos_view", None)
        if pos and hasattr(pos, action_name):
            getattr(pos, action_name)()
        elif hasattr(dashboard.parent_window, action_name):
            getattr(dashboard.parent_window, action_name)()
        else:
            not_implemented(fallback_title)()
            
    sales.add_dropdown_action("Operations", "POS", lambda: _run_pos_action("switch_to_pos", "POS"))
    sales.add_dropdown_action("Operations", "Quotations", open_quotations)
    sales.add_dropdown_action("Operations", "Credit Notes", open_credit_notes_dialog)
    sales.add_dropdown_action("Operations", "Sales Order", lambda: _run_pos_action("_open_sales_order_list", "Sales Order"))
    from views.inventory.shift_reconciliation_screen import ShiftReconciliationScreen
    sales.add_dropdown_screen("Operations", "Shift Reconciliation", ShiftReconciliationScreen(dashboard.parent_window))
    sales.add_dropdown_action("Operations", "Sales Invoice List", lambda: _run_pos_action("_open_sales_list", "Sales Invoices"))
    sales.add_dropdown_action("Operations", "Sales Report", lambda: _run_pos_action("_open_sales_report_tab", "Sales Report"))
    sales.add_dropdown_action("Operations", "Payments", lambda: _run_pos_action("_open_customer_payment_entry", "Payments"))
    sales.add_dropdown_action("Operations", "Reprint Shift Reconciliation", lambda: _run_pos_action("_open_shift_reprint", "Reprint Shift Reconciliation"))
    
    def open_customers():
        from views.dialogs.settings_dialog import CustomerDialog
        from PySide6.QtCore import Qt
        dlg = CustomerDialog(dashboard.parent_window)
        dlg.setWindowState(Qt.WindowMaximized)
        dlg.exec()
        
    sales.add_dropdown_action("Master", "Customers", open_customers)
    sales.add_dropdown_action("Master", "Customer Groups", dashboard._sd_action("CustomerGroupDialog"))
    sales.add_dropdown_action("Master", "Price Lists", dashboard._sd_action("PriceListDialog"))
    
    sales.add_dropdown_screen("Reporting", "Shift List", dashboard._build_shift_history_tab())
    sales.add_dropdown_action("Reporting", "Sales Invoices", lambda: _run_pos_action("_open_sales_list", "Sales Invoices"))
    sales.add_dropdown_action("Reporting", "Sales Orders", lambda: _run_pos_action("_open_sales_order_list", "Sales Orders"))
    sales.add_dropdown_action("Reporting", "Sales Report", lambda: _run_pos_action("_open_sales_report_tab", "Sales Report"))
    
    def open_report_template():
        from PySide6.QtWidgets import QDialog, QVBoxLayout
        from PySide6.QtCore import Qt
        from views.reports.report_template import ReportTemplate
        dlg = QDialog(dashboard.parent_window)
        dlg.setWindowTitle("Inventory List")
        dlg.setWindowState(Qt.WindowMaximized)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(0, 0, 0, 0)
        
        report = ReportTemplate("Inventory List", dlg)
        report.set_headers(["Item Code", "Product Name", "Category", "On Hand", "Unit Price"])
        report.set_data([
            ["ITM001", "Coca Cola 330ml", "Beverages", 145, "$1.50"],
            ["ITM002", "Lays Classic", "Snacks", 89, "$2.00"],
            ["ITM003", "Heineken 500ml", "Alcohol", 42, "$3.50"],
            ["ITM004", "Red Bull 250ml", "Beverages", 210, "$2.50"],
            ["ITM005", "Doritos Nacho", "Snacks", 15, "$2.20"]
        ])
        
        lay.addWidget(report)
        dlg.exec()
        
    # sales.add_dropdown_action("Reporting", "Inventory List Template", open_report_template)

    from views.reports.consumed_items_report_page import ConsumedItemsReportPage
    sales.add_dropdown_screen("Reporting", "Consumed Items Report", ConsumedItemsReportPage(dashboard.parent_window))
    
    sales.add_dropdown_action("Reporting", "Item Sales", open_item_sales)
    sales.add_dropdown_action("Reporting", "Category Sales", open_category_sales)
    sales.add_dropdown_action("Reporting", "Item Profitability", open_item_profit)
    sales.add_dropdown_action("Reporting", "Category Profitability", open_category_profit)
    sales.add_dropdown_action("Reporting", "Cashier Sales", open_cashier_sales)
    sales.add_dropdown_action("Reporting", "Till Profitability", open_till_profit)
    sales.add_dropdown_action("Reporting", "Daily Avg Profit / Inv", open_daily_avg_profit)
    
    sales.add_dropdown_action("Reporting", "Credit Notes", open_credit_notes_dialog)
    sales.add_dropdown_screen("Reporting", "Recent Sales", dashboard._build_recent_sales_page())
    sales.add_dropdown_action("Reporting", "Quotation", lambda: _run_pos_action("_open_quotation_manager", "Quotation Report"))
    
    def open_payment_methods():
        from views.dialogs.payment_modes_dialog import PaymentModesDialog
        PaymentModesDialog(dashboard.parent_window).exec()

    sales.add_dropdown_action("Configurations", "Payment Methods", open_payment_methods)
    sales.add_dropdown_action("Configurations", "Category Visibility", lambda: dashboard._open_cat_dialog())
    
    modules["Sales"] = sales


    # 2. SUPPLIERS
    suppliers = OdooModuleView("Suppliers", dashboard)
    suppliers.on_back_requested(lambda: dashboard.stack.setCurrentIndex(0))
    
    from views.reports.supplier_dashboard import SupplierDashboardWidget
    suppliers.add_tab_direct("Dashboard", SupplierDashboardWidget(dashboard.parent_window))
    
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

    from views.dialogs.supplier_payment_dialog import ProcessSupplierPaymentDialog
    
    suppliers.add_dropdown_action("Operations", "Purchase Invoices", open_purchase_invoice_dlg)
    suppliers.add_dropdown_action("Operations", "Purchase Returns", open_purchase_return_dlg)
    suppliers.add_dropdown_screen("Operations", "Process Supplier Payment", ProcessSupplierPaymentDialog(dashboard.parent_window))
    suppliers.add_dropdown_action("Reporting", "Purchase Invoices", open_purchase_invoice_reports)
    
    from views.reports.supplier_list_report import SupplierListReport
    suppliers.add_dropdown_screen("Reporting", "Supplier List", SupplierListReport(dashboard.parent_window))

    modules["Suppliers"] = suppliers



    # 4. FINANCE
    finance = OdooModuleView("Finance", dashboard)
    finance.on_back_requested(lambda: dashboard.stack.setCurrentIndex(0))
    finance.add_tab_direct("Dashboard", dashboard._build_finance_dashboard())
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
    

    from views.reports.profit_and_loss_report import ProfitAndLossReport
    finance.add_dropdown_screen("Reporting", "Profit & Loss Reports", ProfitAndLossReport(dashboard.parent_window))
    
    from views.reports.expense_list_report import ExpenseListReport
    finance.add_dropdown_screen("Reporting", "Expenses", ExpenseListReport(dashboard.parent_window))
    
    from views.reports.cash_day_book_report import CashDayBookReport
    from views.reports.cash_ledger_report import CashLedgerReport
    from views.reports.invoice_payment_breakdown_report import InvoicePaymentBreakdownReport
    finance.add_dropdown_screen("Reporting", "Cash Day Book", CashDayBookReport(dashboard.parent_window))
    finance.add_dropdown_screen("Reporting", "Cash Ledger Report", CashLedgerReport(dashboard.parent_window))
    finance.add_dropdown_screen("Reporting", "Invoice Payment Breakdown", InvoicePaymentBreakdownReport(dashboard.parent_window))
    
    from views.reports.management_report import ManagementReportPage
    finance.add_dropdown_screen("Reporting", "Management Report", ManagementReportPage(dashboard.parent_window))

    finance.add_dropdown_action("Reporting", "Sales: Item Sales", open_item_sales)
    finance.add_dropdown_action("Reporting", "Sales: Category Sales", open_category_sales)
    finance.add_dropdown_action("Reporting", "Sales: Item Profitability", open_item_profit)
    finance.add_dropdown_action("Reporting", "Sales: Category Profitability", open_category_profit)
    finance.add_dropdown_action("Reporting", "Sales: Cashier Sales", open_cashier_sales)
    finance.add_dropdown_action("Reporting", "Sales: Till Profitability", open_till_profit)
    finance.add_dropdown_action("Reporting", "Management Report", open_management_report)

    finance.add_dropdown_screen("Operations", "Process Supplier Payment", ProcessSupplierPaymentDialog(dashboard.parent_window))
    
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
    
    modules["Finance"] = finance


    # 5. INVENTORY
    inventory = OdooModuleView("Inventory", dashboard)
    inventory.on_back_requested(lambda: dashboard.stack.setCurrentIndex(0))
    inventory.add_tab_direct("Dashboard", dashboard._build_inventory_dashboard())
    inventory.add_tab_dropdown("Master")
    inventory.add_tab_dropdown("Operations")
    inventory.add_tab_dropdown("Reporting")
    inventory.add_tab_dropdown("Configurations")
    
    stock_tab_idx = inventory.stack.count()
    inventory.stack.addWidget(dashboard._build_stock_tab())
    
    from views.inventory.stock_transfer_screen import StockTransferScreen
    from views.inventory.stock_reconciliation_screen import StockReconciliationScreen
    from views.inventory.stock_adjustments_screen import StockAdjustmentsScreen
    inventory.add_dropdown_screen("Operations", "Stock Take", StockReconciliationScreen(dashboard.parent_window))
    inventory.add_dropdown_screen("Operations", "Stock Adjustments", StockAdjustmentsScreen(dashboard.parent_window))
    
    def open_bundle_dialog():
        from views.dialogs.bundle_dialog import BundleDialog
        BundleDialog(dashboard.parent_window).exec()

    inventory.add_dropdown_action("Operations", "Add Product Bundle", open_bundle_dialog)
    inventory.add_dropdown_screen("Operations", "Stock Transfer", StockTransferScreen(dashboard.parent_window))
    
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

    # 1. Stock Valuation
    inventory.add_dropdown_action("Reporting", "Stock Valuation", open_hist_val)
    
    # 2 & 3. Detailed & Summary Inventory Ledger
    from views.reports.detailed_inventory_ledger import DetailedInventoryLedger
    from views.reports.summary_inventory_ledger import SummaryInventoryLedger
    inventory.add_dropdown_screen("Reporting", "Detailed Inventory Ledger", DetailedInventoryLedger(dashboard.parent_window))
    inventory.add_dropdown_screen("Reporting", "Summary Inventory Ledger", SummaryInventoryLedger(dashboard.parent_window))

    # 4 & 5. Breakages & Wastages
    inventory.add_dropdown_action("Reporting", "Breakages Report", open_breakages_report)
    inventory.add_dropdown_action("Reporting", "Wastages Report", open_wastages_report)

    # 6, 7 & 8. Low Stock, Expired Goods, Batch Stock
    inventory.add_dropdown_action("Reporting", "Low Stock Report", open_low_stock)
    inventory.add_dropdown_action("Reporting", "Expired Goods", open_expired_goods)
    inventory.add_dropdown_action("Reporting", "Batch Stock Report", open_batch_stock)

    # 9. Adjustment Report
    inventory.add_dropdown_action("Reporting", "Adjustment Report", open_adjustments_report)

    # 10. Disabled Items Reports
    from views.reports.disabled_items_report import DisabledItemsReport
    inventory.add_dropdown_screen("Reporting", "Disabled Items Reports", DisabledItemsReport(dashboard.parent_window))
    
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
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(dashboard.parent_window, "Error", f"Could not open Dosages:\\n{e}")

    inventory.add_dropdown_action("Configurations", "Warehouses", dashboard._sd_action("WarehouseDialog"))
    inventory.add_dropdown_action("Configurations", "UOM", open_uom)
    
    from views.inventory.batches_screen import BatchesScreen
    inventory.add_dropdown_screen("Configurations", "Batches", BatchesScreen(dashboard.parent_window))
    
    
    
    try:
        from settings.pharmacy_settings import get_pharmacy_mode
        pharmacy_mode_enabled = bool(get_pharmacy_mode())
    except:
        pharmacy_mode_enabled = False
        
    if pharmacy_mode_enabled:
        inventory.add_dropdown_action("Configurations", "Dosages", open_dosages)
        
    inventory.add_dropdown_action("Configurations", "Variants", not_implemented("Variants"))
    
    from views.pages.costing_method_page import CostingMethodPage
    inventory.add_dropdown_screen("Configurations", "Cost Method", CostingMethodPage(dashboard.parent_window))
    
    modules["Inventory"] = inventory


    # 6. EXPENSES (Matches Finance -> Operations -> Expenses)
    expenses = OdooModuleView("Expenses", dashboard)
    expenses.on_back_requested(lambda: dashboard.stack.setCurrentIndex(0))
    expenses.add_tab_direct("Dashboard", dashboard._build_expenses_dashboard())
    
    def open_process_expense():
        from views.dialogs.expense_dialog import ProcessExpenseDialog
        ProcessExpenseDialog(dashboard.parent_window).exec()
        
    expenses.add_tab_dropdown("Master")
    expenses.add_dropdown_action("Master", "Expenses", open_process_expense)
    
    expenses.add_tab_dropdown("Operations")
    expenses.add_dropdown_screen("Operations", "Shift History", dashboard._build_shift_history_tab())
    expenses.add_dropdown_action("Operations", "Process Expense", open_process_expense)
    
    expenses.add_tab_dropdown("Reporting")
    from views.reports.expense_list_report import ExpenseListReport
    expenses.add_dropdown_screen("Reporting", "Expenses", ExpenseListReport(dashboard.parent_window))
    
    expenses.add_tab_dropdown("Configurations")
    modules["Expenses"] = expenses


    # 7. SETTINGS
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
    
    from views.dialogs.backup_settings_dialog import BackupSettingsView
    settings.add_dropdown_screen("Configurations", "Backup & Restore", BackupSettingsView(dashboard.parent_window))
    
    modules["Settings"] = settings

    return modules
