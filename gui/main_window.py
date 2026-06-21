from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.bot_controller import CONFIG_PATH, BotController


class MainWindow(QMainWindow):
    def __init__(self, bot_controller: BotController):
        super().__init__()
        self._bot = bot_controller
        self._setup_ui()
        self._load_config_into_editor()

    def _setup_ui(self):
        self.setWindowTitle("YouTube Chat Bot - TV IEBT")
        self.setMinimumSize(600, 400)
        self.resize(720, 480)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # ── Header / controls ──
        header = QHBoxLayout()
        self._status_label = QLabel("Status: Parado")
        self._status_label.setStyleSheet(
            "font-weight: bold; font-size: 14px; padding: 4px;"
        )
        self._toggle_btn = QPushButton("Iniciar Bot")
        self._toggle_btn.setMinimumWidth(120)
        self._toggle_btn.clicked.connect(self._toggle_bot)

        header.addWidget(self._status_label)
        header.addStretch()
        header.addWidget(self._toggle_btn)
        layout.addLayout(header)

        # ── Tabs ──
        tabs = QTabWidget()

        # Log tab
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(2000)
        f = self._log_view.font()
        f.setPointSize(10)
        self._log_view.setFont(f)
        log_layout.addWidget(self._log_view)
        tabs.addTab(log_widget, "Log")

        # Config tab
        config_widget = QWidget()
        config_layout = QVBoxLayout(config_widget)
        config_layout.setContentsMargins(0, 0, 0, 0)
        self._config_edit = QTextEdit()
        f = self._config_edit.font()
        f.setPointSize(10)
        self._config_edit.setFont(f)
        config_layout.addWidget(self._config_edit)
        btn_row = QHBoxLayout()
        reload_btn = QPushButton("Recarregar")
        reload_btn.clicked.connect(self._load_config_into_editor)
        save_btn = QPushButton("Salvar")
        save_btn.clicked.connect(self._save_config)
        btn_row.addStretch()
        btn_row.addWidget(reload_btn)
        btn_row.addWidget(save_btn)
        config_layout.addLayout(btn_row)
        tabs.addTab(config_widget, "Config")

        layout.addWidget(tabs)

    def _toggle_bot(self):
        if self._bot.is_running:
            self._bot.stop()
            self._toggle_btn.setText("Iniciar Bot")
        else:
            self._bot.start()
            self._toggle_btn.setText("Parar Bot")

    def update_status(self, status: str):
        labels = {
            "rodando": ("Status: Rodando", "color: green;"),
            "parado": ("Status: Parado", "color: gray;"),
            "erro": ("Status: Erro", "color: red;"),
            "live_detectada": ("Status: Live Detectada", "color: blue;"),
        }
        text, style = labels.get(
            status, (f"Status: {status}", "")
        )
        self._status_label.setText(text)
        combined = "font-weight: bold; font-size: 14px; padding: 4px;" + style
        self._status_label.setStyleSheet(combined)
        if status in ("parado", "erro"):
            self._toggle_btn.setText("Iniciar Bot")

    def append_log(self, msg: str):
        self._log_view.appendPlainText(msg)
        cursor = self._log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._log_view.setTextCursor(cursor)

    def _load_config_into_editor(self):
        try:
            text = CONFIG_PATH.read_text(encoding="utf-8")
            self._config_edit.setPlainText(text)
        except Exception as e:
            self.append_log(f"Erro ao carregar config: {e}")

    def _save_config(self):
        try:
            CONFIG_PATH.write_text(
                self._config_edit.toPlainText(), encoding="utf-8"
            )
            self.append_log("Configuracao salva com sucesso")
        except Exception as e:
            self.append_log(f"Erro ao salvar config: {e}")

    def closeEvent(self, event: QCloseEvent):
        event.ignore()
        self.hide()
