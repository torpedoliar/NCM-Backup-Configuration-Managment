from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout


class Sidebar(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("Sidebar")
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        self.brand = QLabel("NCM OPS_")
        self.brand.setObjectName("Brand")
        layout.addWidget(self.brand)

        self.subtitle = QLabel("NETWORK CONFIG MGR")
        self.subtitle.setObjectName("Marker")
        layout.addWidget(self.subtitle)

        self.version_tag = QLabel("V3.5.7 / PROD")
        self.version_tag.setObjectName("Marker")
        layout.addWidget(self.version_tag)

        self.buttons: dict[str, QPushButton] = {}
        for label in ["Dashboard", "Switches", "Credentials", "History", "Diff", "Schedules", "Users", "Settings"]:
            button = QPushButton(label)
            self.buttons[label] = button
            layout.addWidget(button)
        layout.addStretch()
