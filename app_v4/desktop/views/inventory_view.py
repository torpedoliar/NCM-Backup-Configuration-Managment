from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QTableView, QVBoxLayout, QWidget


class InventoryView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.title = QLabel("Inventory")
        layout.addWidget(self.title)
        layout.addWidget(QPushButton("Add switch"))
        layout.addWidget(QTableView())
