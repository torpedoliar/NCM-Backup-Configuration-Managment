"""Single-instance guard for the desktop shell.

Closing the window leaves NCM v4 running in the tray by design, so a second
launch used to start a second backend: it found port 8443 busy and showed a
"Port in use" dialog (often hidden behind other windows) or, after picking
another port, ran two schedulers against the same data/app.db.

The guard makes a second launch surface the window that is already running.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

SERVER_NAME = "ncm-v4-desktop-single-instance"
_CONNECT_TIMEOUT_MS = 400


def activate_running_instance() -> bool:
    """True when another instance is already running (and was asked to show)."""
    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    if not socket.waitForConnected(_CONNECT_TIMEOUT_MS):
        return False
    try:
        socket.write(b"show")
        socket.flush()
        socket.waitForBytesWritten(_CONNECT_TIMEOUT_MS)
    finally:
        socket.disconnectFromServer()
    return True


class SingleInstanceServer(QObject):
    """Owns the local socket; emits activated() when a second launch asks for the window."""

    activated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # A crashed process leaves the socket behind; clear it before listening.
        QLocalServer.removeServer(SERVER_NAME)
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_new_connection)
        self._listening = self._server.listen(SERVER_NAME)

    @property
    def listening(self) -> bool:
        return self._listening

    def _on_new_connection(self) -> None:
        while self._server.hasPendingConnections():
            connection = self._server.nextPendingConnection()
            if connection is None:
                continue
            connection.disconnected.connect(connection.deleteLater)
            self.activated.emit()
