from PyQt6.QtWidgets import QPlainTextEdit

from ....i18n import _
from ...workers import strip_ansi


class LogWidget(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMinimumHeight(180)
        font = self.font()
        font.setFamily("monospace")
        self.setFont(font)
        self._user_scrolled = False
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def _on_scroll(self, value: int) -> None:
        self._user_scrolled = value < self.verticalScrollBar().maximum()

    def append_output(self, text: str) -> None:
        for line in strip_ansi(text).splitlines():
            self.appendPlainText(line)
        if not self._user_scrolled:
            sb = self.verticalScrollBar()
            sb.setValue(sb.maximum())

    def append_command(self, cmd: list[str]) -> None:
        self.append_output(_("$ %s\n") % " ".join(cmd))
