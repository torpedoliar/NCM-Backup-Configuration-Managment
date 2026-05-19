from __future__ import annotations

import logging
import threading

import servicemanager
import uvicorn
import win32event
import win32service
import win32serviceutil

from app_v4.core.config import Settings
from app_v4.service.main import uvicorn_kwargs

logger = logging.getLogger(__name__)


class NcmV4BackendService(win32serviceutil.ServiceFramework):
    _svc_name_ = "NCMv4Backend"
    _svc_display_name_ = "NCM v4 Backend Service"
    _svc_description_ = "NCM v4 FastAPI backend, scheduler host, and web server."

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.server: uvicorn.Server | None = None
        self.thread: threading.Thread | None = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self.server is not None:
            self.server.should_exit = True
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        settings = Settings()
        kwargs = uvicorn_kwargs(settings)
        config = uvicorn.Config(**kwargs)
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
        if self.thread is not None:
            self.thread.join(timeout=10)


def main() -> None:
    win32serviceutil.HandleCommandLine(NcmV4BackendService)


if __name__ == "__main__":
    main()
