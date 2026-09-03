import re

text = open('views/main_window.py', encoding='utf-8').read()

# 1. Restore Headers
old1 = """self.stock_report.set_headers([
            "", "Part No.", "Product Name", "Category",
            "Qty on Hand", "Cost Price", "Sale Price",
            "Value @ Cost", "Value @ Sale", "Potential Profit"
        ])
        
        self.stock_report.table.setColumnHidden(0, True)
        
        # Adjust table headers resize mode
        hh = self.stock_report.table.horizontalHeader()
        hh.setDefaultAlignment(Qt.AlignCenter)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)"""

new1 = """self.stock_report.set_headers([
            "Part No.", "Product Name", "Category",
            "Qty on Hand", "Cost Price", "Sale Price",
            "Value @ Cost", "Value @ Sale", "Potential Profit"
        ])
        
        # Adjust table headers resize mode
        hh = self.stock_report.table.horizontalHeader()
        hh.setDefaultAlignment(Qt.AlignCenter)
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents) # Part No
        hh.setSectionResizeMode(1, QHeaderView.Stretch)"""

text = text.replace(old1, new1)

# 2. Restore vals and alignments in _render_stock
old2 = """            vals = [
                "",
                p.get("part_no", ""),
                p.get("name", ""),
                p.get("category", ""),
                f"{qty:.2f}",
                f"${cost:.2f}",
                f"${sell:.2f}",
                f"${val_cost:.2f}",
                f"${val_sell:.2f}",
                f"${(val_sell - val_cost):.2f}"
            ]
            alignments = [
                Qt.AlignCenter,
                Qt.AlignCenter,
                Qt.AlignCenter,
                Qt.AlignCenter,
                Qt.AlignCenter,
                Qt.AlignRight | Qt.AlignVCenter,
                Qt.AlignRight | Qt.AlignVCenter,
                Qt.AlignRight | Qt.AlignVCenter,
                Qt.AlignRight | Qt.AlignVCenter,
                Qt.AlignRight | Qt.AlignVCenter,
            ]
            
            container = QWidget()
            l = QHBoxLayout(container)
            l.setContentsMargins(10, 0, 0, 0)
            cb = QCheckBox()
            l.addWidget(cb)
            self.stock_report.table.setCellWidget(r, 0, container)
            
            for ci, (val, aln) in enumerate(zip(vals, alignments)):
                if ci == 0: continue
                if ci == 1:
                    it.setData(Qt.UserRole, p)
                if ci == 4 and qty <= 5:
                    it.setForeground(QColor(DANGER))
                if ci == 7:
                    it.setForeground(QColor(NAVY))
                if ci == 8:
                    it.setForeground(QColor(ACCENT))"""

new2 = """            vals = [
                p.get("part_no", ""),
                p.get("name", ""),
                p.get("category", ""),
                f"{qty:.2f}",
                f"${cost:.2f}",
                f"${sell:.2f}",
                f"${val_cost:.2f}",
                f"${val_sell:.2f}",
                f"${(val_sell - val_cost):.2f}"
            ]
            alignments = [
                Qt.AlignCenter,
                Qt.AlignCenter,
                Qt.AlignCenter,
                Qt.AlignCenter,
                Qt.AlignRight | Qt.AlignVCenter,
                Qt.AlignRight | Qt.AlignVCenter,
                Qt.AlignRight | Qt.AlignVCenter,
                Qt.AlignRight | Qt.AlignVCenter,
                Qt.AlignRight | Qt.AlignVCenter,
            ]
            
            for ci, (val, aln) in enumerate(zip(vals, alignments)):
                it = QTableWidgetItem(val)
                it.setTextAlignment(aln)
                if ci == 0:
                    it.setData(Qt.UserRole, p)
                if ci == 3 and qty <= 5:
                    it.setForeground(QColor(DANGER))
                if ci == 6:
                    it.setForeground(QColor(NAVY))
                if ci == 7:
                    it.setForeground(QColor(ACCENT))"""

text = text.replace(old2, new2)

# 3. Restore the buttons in _build_tab_master
old3 = """        self._stock_select_btn = QPushButton(" Select")
        self._stock_select_btn.setIcon(qta.icon("fa5s.check-square", color="white"))
        self._stock_select_btn.setFixedHeight(28)
        self._stock_select_btn.setCursor(Qt.PointingHandCursor)
        self._stock_select_btn.setStyleSheet(f"QPushButton {{ background-color: {NAVY_2}; color: white; border: none; border-radius: 4px; padding: 0 12px; font-weight: bold; font-size: 11px; }} QPushButton:hover {{ background-color: {NAVY_3}; }}")
        
        self._stock_delete_btn = QPushButton(" Delete")
        self._stock_delete_btn.setIcon(qta.icon("fa5s.trash", color="white"))
        self._stock_delete_btn.setFixedHeight(28)
        self._stock_delete_btn.setCursor(Qt.PointingHandCursor)
        self._stock_delete_btn.setStyleSheet(f"QPushButton {{ background-color: {DANGER}; color: white; border: none; border-radius: 4px; padding: 0 12px; font-weight: bold; font-size: 11px; }} QPushButton:hover {{ background-color: {DANGER_H}; }}")

        # Insert buttons next to the default add button
        idx_add = self.stock_report.filters_layout.indexOf(self.stock_report.btn_add)
        self.stock_report.filters_layout.insertWidget(idx_add + 1, self._stock_edit_btn)
        self.stock_report.filters_layout.insertWidget(idx_add + 2, self._stock_select_btn)
        self.stock_report.filters_layout.insertWidget(idx_add + 3, self._stock_delete_btn)"""

new3 = """        self._stock_delete_btn = QPushButton(" Delete")
        self._stock_delete_btn.setIcon(qta.icon("fa5s.trash", color="white"))
        self._stock_delete_btn.setFixedHeight(28)
        self._stock_delete_btn.setCursor(Qt.PointingHandCursor)
        self._stock_delete_btn.setStyleSheet(f"QPushButton {{ background-color: {DANGER}; color: white; border: none; border-radius: 4px; padding: 0 12px; font-weight: bold; font-size: 11px; }} QPushButton:hover {{ background-color: {DANGER_H}; }}")
        self._stock_delete_btn.setVisible(False)

        # Insert buttons next to the default add button
        idx_add = self.stock_report.filters_layout.indexOf(self.stock_report.btn_add)
        self.stock_report.filters_layout.insertWidget(idx_add + 1, self._stock_edit_btn)
        self.stock_report.filters_layout.insertWidget(idx_add + 2, self._stock_delete_btn)"""

text = text.replace(old3, new3)

# 4. Restore the connections
old4 = """        self._stock_selection_mode = False
        def _on_stock_select():
            self._stock_selection_mode = not self._stock_selection_mode
            if self._stock_selection_mode:
                self.stock_report.table.setColumnWidth(0, 40)
                self._stock_select_btn.setText(" Cancel Select")
                self._stock_delete_btn.setText(" Delete Selected")
                for r in range(self.stock_report.table.rowCount()):
                    container = self.stock_report.table.cellWidget(r, 0)
                    if container:
                        cb = container.findChild(QCheckBox)
                        if cb: cb.setChecked(False)
            else:
                self.stock_report.table.setColumnWidth(0, 0)
                self._stock_select_btn.setText(" Select")
                self._stock_delete_btn.setText(" Delete")
                
        def _on_stock_delete():
            if self._stock_selection_mode:
                to_delete = []
                for r in range(self.stock_report.table.rowCount()):
                    container = self.stock_report.table.cellWidget(r, 0)
                    if container:
                        cb = container.findChild(QCheckBox)
                        if cb and cb.isChecked():
                            p = self.stock_report.table.item(r, 1).data(Qt.UserRole)
                            if p: to_delete.append(p)
                if not to_delete: return
                ans = QMessageBox.question(self, "Delete Multiple", f"Are you sure you want to delete {len(to_delete)} products?", QMessageBox.Yes | QMessageBox.No)
                if ans == QMessageBox.Yes:
                    try:
                        from database.db import get_connection
                        conn = get_connection()
                        cur = conn.cursor()
                        for p in to_delete:
                            cur.execute("UPDATE products SET active = 0 WHERE id = ?", (p['id'],))
                        conn.commit()
                        conn.close()
                        self._load_stock_data()
                        _on_stock_select() # Turn off selection mode
                    except Exception as e:
                        QMessageBox.critical(self, "Deletion Failed", str(e))
            else:
                row = self.stock_report.table.currentRow()
                if row < 0: return
                item = self.stock_report.table.item(row, 1)
                if not item: return
                p = item.data(Qt.UserRole)
                if not p: return
                ans = QMessageBox.question(self, "Delete", f"Are you sure you want to delete {p.get('part_no', '')}?", QMessageBox.Yes | QMessageBox.No)
                if ans == QMessageBox.Yes:
                    try:
                        from database.db import get_connection
                        conn = get_connection()
                        cur = conn.cursor()
                        cur.execute("UPDATE products SET active = 0 WHERE id = ?", (p['id'],))
                        conn.commit()
                        conn.close()
                        self._load_stock_data()
                    except Exception as e:
                        QMessageBox.critical(self, "Deletion Failed", str(e))

        self._stock_select_btn.clicked.connect(_on_stock_select)
        self._stock_delete_btn.clicked.connect(_on_stock_delete)
        
        def _on_stock_selection_changed():
            has_selection = len(self.stock_report.table.selectedItems()) > 0
            self._stock_edit_btn.setVisible(has_selection)"""

new4 = """        def _on_stock_delete():
            row = self.stock_report.table.currentRow()
            if row < 0: return
            item = self.stock_report.table.item(row, 0)
            if not item: return
            p = item.data(Qt.UserRole)
            if not p: return
            ans = QMessageBox.question(self, "Delete Product", f"Are you sure you want to delete '{p.get('part_no', '')}'?", QMessageBox.Yes | QMessageBox.No)
            if ans == QMessageBox.Yes:
                try:
                    from database.db import get_connection
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("UPDATE products SET active = 0 WHERE id = ?", (p['id'],))
                    conn.commit()
                    conn.close()
                    self._load_stock_data()
                except Exception as e:
                    QMessageBox.critical(self, "Deletion Failed", str(e))

        self._stock_delete_btn.clicked.connect(_on_stock_delete)
        
        def _on_stock_selection_changed():
            has_selection = len(self.stock_report.table.selectedItems()) > 0
            self._stock_edit_btn.setVisible(has_selection)
            self._stock_delete_btn.setVisible(has_selection)"""

text = text.replace(old4, new4)

open('views/main_window.py', 'w', encoding='utf-8').write(text)
print("SUCCESS")
