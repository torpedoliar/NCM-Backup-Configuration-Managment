from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QTableView, QVBoxLayout, QWidget


class SchedulesView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.title = QLabel("Schedules")
        layout.addWidget(self.title)
        layout.addWidget(QPushButton("Add schedule"))
        layout.addWidget(QTableView())
