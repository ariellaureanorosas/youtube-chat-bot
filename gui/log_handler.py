import logging

from PySide6.QtCore import QObject, Signal


class QtLogHandler(logging.Handler, QObject):
    log_received = Signal(str)

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_received.emit(msg)
        except Exception:
            self.handleError(record)
