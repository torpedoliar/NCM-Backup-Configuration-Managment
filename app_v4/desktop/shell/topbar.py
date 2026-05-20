from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel


class Topbar(QFrame):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        self.breadcrumb = QLabel("monitoring / Dashboard")
        self.pulse = QLabel("service pulse · pending")
        layout.addWidget(self.breadcrumb)
        layout.addStretch()
        layout.addWidget(self.pulse)
