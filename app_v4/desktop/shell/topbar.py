from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel


class Topbar(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("Topbar")
        layout = QHBoxLayout(self)
        self.breadcrumb = QLabel("monitoring / Dashboard")
        self.breadcrumb.setObjectName("Marker")
        self.service_pulse = QLabel("SERVICE / RUNNING")
        self.service_pulse.setObjectName("ServicePulse")
        self.pulse = self.service_pulse
        layout.addWidget(self.breadcrumb)
        layout.addStretch()
        layout.addWidget(self.service_pulse)
