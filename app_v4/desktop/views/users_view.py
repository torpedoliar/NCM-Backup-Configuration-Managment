from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QTableView, QVBoxLayout, QWidget


class UsersView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.title = QLabel("Users")
        layout.addWidget(self.title)
        layout.addWidget(QPushButton("Add user"))
        layout.addWidget(QTableView())
