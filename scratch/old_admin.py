class AdminDashboard(QWidget):
    def __init__(self, parent_window=None, user=None):
        super().__init__()
        self.parent_window = parent_window
        self.user = user or {}
        self._build()
        self._load_data()

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        nav = QWidget(); nav.setFixedHeight(54)
        nav.setStyleSheet(f"background-color: {NAVY};")
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(20, 8, 20, 8); nav_layout.setSpacing(12)

        logo = QLabel("POS System")
        logo.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {WHITE}; background: transparent; letter-spacing: 1px;")
        nav_layout.addWidget(logo)

        badge = QLabel("ADMIN")
        badge.setStyleSheet(f"""
            background-color: {ACCENT}; color: {WHITE};
            border-radius: 4px; font-size: 10px; font-weight: bold;
            padding: 2px 8px; letter-spacing: 1px;
        """)
        nav_layout.addWidget(badge); nav_layout.addStretch()

        date_lbl = QLabel(QDate.currentDate().toString("dd MMM yyyy"))
        date_lbl.setStyleSheet(f"font-size: 12px; color: {NAVY}; background: transparent;")
        nav_layout.addWidget(date_lbl); nav_layout.addSpacing(16)

        logout_btn = navy_btn("Logout", height=30, width=72, color=DANGER, hover=DANGER_H)
        if self.parent_window:
            logout_btn.clicked.connect(self.parent_window._logout)
        nav_layout.addWidget(logout_btn)

        root.addWidget(nav); root.addWidget(hr())

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {OFF_WHITE}; }}")

        body = QWidget(); body.setStyleSheet(f"background: {OFF_WHITE};")
        body_layout = QVBoxLayout(body)
        body_layout.setSpacing(20); body_layout.setContentsMargins(24, 20, 24, 24)

        body_layout.addWidget(self._section_label("Today at a Glance"))
        body_layout.addLayout(self._build_stats_row())

        content_row = QHBoxLayout(); content_row.setSpacing(20)

        left_col = QVBoxLayout(); left_col.setSpacing(12)
        left_col.addWidget(self._section_label("Recent Sales  (Today)"))
        left_col.addWidget(self._build_sales_table())
        content_row.addLayout(left_col, 3)

        right_col = QVBoxLayout(); right_col.setSpacing(12)
        right_col.addWidget(self._section_label("Quick Actions"))
        right_col.addWidget(self._build_quick_actions())
        right_col.addWidget(self._section_label("Stock Alerts"))
        right_col.addWidget(self._build_stock_alerts())
        right_col.addStretch()
        content_row.addLayout(right_col, 1)

        body_layout.addLayout(content_row)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

    def _section_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            font-size: 13px; font-weight: bold; color: {NAVY};
            background: transparent;
            border-left: 3px solid {ACCENT}; padding-left: 8px;
        """)
        return lbl

    def _build_stats_row(self):
        layout = QHBoxLayout(); layout.setSpacing(14)
        self._stat_widgets = {}

        for key, label, initial, color in [
            ("revenue",     "Today's Revenue",  "$0.00",    NAVY),
            ("txn_count",   "Transactions",     "0",        ACCENT),
            ("items_sold",  "Items Sold",        "0",        SUCCESS),
            ("top_method",  "Top Payment",       "—",        AMBER),
        ]:
            card = QWidget()
            card.setStyleSheet(f"""
                QWidget {{
                    background-color: {WHITE};
                    border: 1px solid {BORDER};
                    border-radius: 8px;
                    border-top: 3px solid {color};
                }}
            """)
            card.setFixedHeight(90)
            cl = QVBoxLayout(card); cl.setContentsMargins(16, 12, 16, 12); cl.setSpacing(4)
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent; font-weight: bold; letter-spacing: 0.5px;")
            val = QLabel(initial)
            val.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: bold; background: transparent;")
            cl.addWidget(lbl); cl.addWidget(val)
            layout.addWidget(card, 1)
            self._stat_widgets[key] = val
        return layout

    def _build_sales_table(self):
        self.sales_table = QTableWidget(0, 6)
        self.sales_table.setHorizontalHeaderLabels(["Invoice #", "Time", "Cashier", "Method", "Total", "Synced"])
        hh = self.sales_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed);  self.sales_table.setColumnWidth(0, 100)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.Fixed);  self.sales_table.setColumnWidth(3, 90)
        hh.setSectionResizeMode(4, QHeaderView.Fixed);  self.sales_table.setColumnWidth(4, 100)
        hh.setSectionResizeMode(5, QHeaderView.Fixed);  self.sales_table.setColumnWidth(5, 70)
        self.sales_table.verticalHeader().setVisible(False)
        self.sales_table.setAlternatingRowColors(True)
        self.sales_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.sales_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sales_table.setFixedHeight(260)
        self.sales_table.setStyleSheet(f"""
            QTableWidget {{ background: {WHITE}; border: 1px solid {BORDER};
                gridline-color: {LIGHT}; outline: none; }}
            QTableWidget::item           {{ padding: 6px 8px; }}
            QTableWidget::item:selected  {{ background-color: {ACCENT}; color: {WHITE}; }}
            QTableWidget::item:alternate {{ background-color: {ROW_ALT}; }}
            QHeaderView::section {{
                background-color: {NAVY}; color: {WHITE};
                padding: 8px; border: none; border-right: 1px solid {NAVY_2};
                font-size: 11px; font-weight: bold;
            }}
        """)
        return self.sales_table

    def _build_quick_actions(self):
        card = QWidget()
        card.setStyleSheet(f"QWidget {{ background-color: {WHITE}; border: 1px solid {BORDER}; border-radius: 8px; }}")
        cl = QVBoxLayout(card); cl.setContentsMargins(16, 14, 16, 14); cl.setSpacing(8)

        actions = [
            ("Sync Users",      self._open_user_sync,                 NAVY_3),
            ("Stock File",      self._open_stock,                     NAVY),
            ("Sales History",   self._open_sales_history,             NAVY_3),
            ("Day Shift",       self._open_day_shift,                 NAVY_2),
            ("Companies",       lambda: self._open_settings_at(1),    MUTED),
            ("Customer Groups", lambda: self._open_settings_at(2),    MUTED),
            ("Warehouses",      lambda: self._open_settings_at(3),    MUTED),
            ("Cost Centers",    lambda: self._open_settings_at(4),    MUTED),
            ("Price Lists",     lambda: self._open_settings_at(5),    MUTED),
            ("Customers",       lambda: self._open_settings_at(6),    MUTED),
            ("Refresh Data",    self._load_data,                      SUCCESS),
        ]
        for label, handler, color in actions:
            btn = QPushButton(label)
            btn.setFixedHeight(38)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color}14; color: {color};
                    border: 1px solid {color}44; border-radius: 5px;
                    font-size: 13px; font-weight: bold;
                    text-align: left; padding: 0 14px;
                }}
                QPushButton:hover {{ background-color: {color}; color: {WHITE}; border-color: {color}; }}
            """)
            btn.clicked.connect(handler)
            cl.addWidget(btn)
        return card

    def _build_stock_alerts(self):
        self._stock_alert_widget = QWidget()
        self._stock_alert_widget.setStyleSheet(f"QWidget {{ background-color: {WHITE}; border: 1px solid {BORDER}; border-radius: 8px; }}")
        self._stock_alert_layout = QVBoxLayout(self._stock_alert_widget)
        self._stock_alert_layout.setContentsMargins(14, 12, 14, 12); self._stock_alert_layout.setSpacing(6)
        lbl = QLabel("No low-stock alerts"); lbl.setStyleSheet(f"color: {MUTED}; font-size: 12px; background: transparent;")
        self._stock_alert_layout.addWidget(lbl)
        return self._stock_alert_widget

    def _load_data(self):
        try:
            from models.sale import get_today_sales, get_today_total, get_today_total_by_method
            sales   = get_today_sales(); total = get_today_total()
            by_meth = get_today_total_by_method()
            top_m   = max(by_meth, key=by_meth.get) if by_meth else "—"
            items   = sum(1 for _ in sales)
        except Exception:
            sales, total, top_m, items = [], 0.0, "Cash", 0

        self._stat_widgets["revenue"].setText(f"${total:,.2f}")
        self._stat_widgets["txn_count"].setText(str(len(sales)))
        self._stat_widgets["items_sold"].setText(str(items))
        self._stat_widgets["top_method"].setText(top_m)

        self.sales_table.setRowCount(0)
        for s in sales[:50]:
            r = self.sales_table.rowCount(); self.sales_table.insertRow(r)
            for c, (key, fmt) in enumerate([
                ("number", lambda v: f"#{v}"),
                ("time",   lambda v: str(v)),
                ("user",   lambda v: str(v)),
                ("method", lambda v: str(v)),
                ("total",  lambda v: f"${v:.2f}"),
                ("synced", lambda v: "✓" if v else "—"),
            ]):
                raw = s.get(key, ""); text = fmt(raw)
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter if c != 2 else Qt.AlignLeft | Qt.AlignVCenter)
                if key == "total": item.setForeground(QColor(ACCENT))
                elif key == "synced": item.setForeground(QColor(SUCCESS if s.get("synced") else MUTED))
                self.sales_table.setItem(r, c, item)
            self.sales_table.setRowHeight(r, 34)

        while self._stock_alert_layout.count():
            item = self._stock_alert_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        try:
            from models.product import get_all_products
            low = [p for p in get_all_products() if p["stock"] <= 5]
        except Exception:
            low = []

        if not low:
            lbl = QLabel("✓  All stock levels OK"); lbl.setStyleSheet(f"color: {SUCCESS}; font-size: 12px; background: transparent;")
            self._stock_alert_layout.addWidget(lbl)
        else:
            for p in low[:8]:
                row_w = QWidget(); row_w.setStyleSheet("background: transparent;")
                rh = QHBoxLayout(row_w); rh.setContentsMargins(0, 0, 0, 0)
                nm = QLabel(p["name"]); nm.setStyleSheet(f"color: {DARK_TEXT}; font-size: 12px; background: transparent;")
                st = QLabel(f"Stock: {p['stock']}"); st.setStyleSheet(f"color: {DANGER}; font-size: 12px; font-weight: bold; background: transparent;")
                rh.addWidget(nm, 1); rh.addWidget(st)
                self._stock_alert_layout.addWidget(row_w)

    def _open_user_sync(self):
        try:
            from views.dialogs.user_sync_dialog import UserSyncDialog
            UserSyncDialog(self).exec()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open User Sync:\n{e}")

    def _open_stock(self):
        if _HAS_STOCK: StockFileDialog(self).exec()
        else: coming_soon(self, "Stock File")

    def _open_sales_history(self):
        if _HAS_SALES_LIST: SalesListDialog(self).exec()
        else: coming_soon(self, "Sales History")

    
    def _open_day_shift(self):
        """Requirement 4: Replaces generic save with Close Shift logic"""
        # We pass the user ID for the audit trail
        cashier_id = self.user.get("id") if self.user else None
        
        dlg = ShiftReconciliationDialog(self, cashier_id=cashier_id)
        if dlg.exec() == QDialog.Accepted:
            # Shift successfully closed - Logout to ensure next cashier starts fresh
            if self.parent_window:
                self.parent_window._logout()

    def _open_settings_at(self, page_index: int = 0):
        if _HAS_SETTINGS_DIALOG:
            dlg = SettingsDialog(self, user=self.user)
            dlg._switch(page_index)
            dlg.exec()
        else:
            coming_soon(self, "Settings — add views/dialogs/settings_dialog.py")
