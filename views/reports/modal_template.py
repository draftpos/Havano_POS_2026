from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QTableWidget, QHeaderView, QPushButton
)
from PySide6.QtCore import Qt
import qtawesome as qta

class ModalTemplate(QDialog):
    """
    A template for full-screen action modals (like Stock Take, Adjustments) 
    that require a clean header and custom action fields without standard report filters.
    """
    def __init__(self, title="ACTION MODAL", subtitle="Subtitle description here", parent=None):
        super().__init__(parent)
        self.title_text = title
        self.subtitle_text = subtitle
        
        self.setWindowFlags(Qt.Window | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle(self.title_text)
        self.setStyleSheet("background-color: #f5f8fc;")
        
        self._build_template()

    def _build_template(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # 1. Light Header Frame (matching ReportTemplate)
        self.header_frame = QFrame()
        self.header_frame.setStyleSheet("background-color: #ffffff; border-bottom: 1px solid #e4eaf4;")
        self.header_frame.setFixedHeight(60)
        
        hl = QHBoxLayout(self.header_frame)
        hl.setContentsMargins(15, 8, 15, 6)
        
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        
        self.lbl_title = QLabel(self.title_text)
        self.lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a5fb4; border: none; padding: 0px; margin: 0px; background: transparent;")
        
        self.lbl_subtitle = QLabel(self.subtitle_text)
        self.lbl_subtitle.setStyleSheet("font-size: 11px; color: #666666; border: none; padding: 0px; margin: 0px; background: transparent;")
        
        title_layout.addWidget(self.lbl_title)
        title_layout.addWidget(self.lbl_subtitle)
        title_layout.addStretch()
        
        hl.addLayout(title_layout)
        hl.addStretch()
        
        self.btn_submit = QPushButton(" Submit")
        self.btn_submit.setIcon(qta.icon("fa5s.check-circle", color="white", scale_factor=0.7))
        self.btn_submit.setFixedHeight(30)
        self.btn_submit.setCursor(Qt.PointingHandCursor)
        self.btn_submit.setStyleSheet("""
            QPushButton { background-color: #1a5fb4; color: white; border: none; border-radius: 4px; padding: 0 12px; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background-color: #1c6dd0; }
        """)
        hl.addWidget(self.btn_submit)
        
        self.main_layout.addWidget(self.header_frame)
        
        # 2. Filters / Tools Area (Light)
        self.tools_frame = QFrame()
        self.tools_frame.setStyleSheet("background-color: #ffffff; border-bottom: 1px solid #e4eaf4;")
        self.tools_layout = QHBoxLayout(self.tools_frame)
        self.tools_layout.setContentsMargins(20, 10, 20, 10)
        self.tools_layout.setSpacing(10)
        
        # Child classes can dynamically inject into self.tools_layout
        
        self.main_layout.addWidget(self.tools_frame)
        
        # 3. Table Area
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(20, 15, 20, 20)
        self.content_layout.setSpacing(0)
        
        self.table = QTableWidget(0, 0)
        self.table.setStyleSheet("""
            QTableWidget { gridline-color: #e4eaf4; border: none; background-color: white; font-size: 13px; color: #333333; }
            QHeaderView::section { background-color: #fdfbf7; padding: 8px; border: none; border-bottom: 2px solid #e4eaf4; border-right: 1px solid #e4eaf4; font-weight: bold; font-size: 13px; color: #1a5fb4; }
            QTableWidget::item { padding: 6px; border: none; }
            QTableWidget::item:selected { background-color: #e8f1f8; color: #1a5fb4; }
        """)

        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        
        self.content_layout.addWidget(self.table)
        self.main_layout.addLayout(self.content_layout)

    def set_headers(self, headers):
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
