from PyQt6.QtCore import QEasingCurve, QPropertyAnimation
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)

from ....i18n import _

# Semantic status colors — universally understood, intentionally not theme-derived
_GREEN = "#3fb950"
_RED   = "#f85149"


class ResultWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setVisible(False)
        self._anim = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 10, 0, 4)
        outer.setSpacing(0)

        self._bar = QFrame()
        self._bar.setFixedWidth(3)
        self._bar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        outer.addWidget(self._bar)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(12, 0, 0, 0)
        text_layout.setSpacing(3)

        self._title = QLabel()
        title_font = self._title.font()
        title_font.setBold(True)
        self._title.setFont(title_font)

        self._sub = QLabel()
        self._sub.setWordWrap(True)
        self._sub.setVisible(False)

        text_layout.addWidget(self._title)
        text_layout.addWidget(self._sub)
        outer.addLayout(text_layout)

    def _muted_color(self) -> str:
        wt = self.palette().color(QPalette.ColorRole.WindowText)
        return f"rgba({wt.red()},{wt.green()},{wt.blue()},160)"

    def show_success(self, boot: bool = False) -> None:
        self._bar.setStyleSheet(f"background:{_GREEN};")
        self._title.setStyleSheet(f"color:{_GREEN};")
        self._title.setText(_("Update successful!"))
        if boot:
            self._sub.setStyleSheet(f"color:{self._muted_color()};")
            self._sub.setText(_("Restart to apply the new kernel / bootloader changes."))
            self._sub.setVisible(True)
        else:
            self._sub.setVisible(False)
        self._show()

    def show_failure(self, exit_code: int) -> None:
        self._bar.setStyleSheet(f"background:{_RED};")
        self._title.setStyleSheet(f"color:{_RED};")
        self._title.setText(_("Update failed (exit code %d)") % exit_code)
        self._sub.setVisible(False)
        self._show()

    def _show(self) -> None:
        self.setVisible(True)
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        self._anim = QPropertyAnimation(effect, b"opacity", self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(300)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()
