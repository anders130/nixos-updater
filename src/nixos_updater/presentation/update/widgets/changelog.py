import re

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QCursor, QDesktopServices, QPalette
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ....i18n import _
from ...workers import HomepageWorker

_UPD_MAJOR = (86,  156, 214)
_UPD_MINOR = (120, 180, 220)
_UPD_PATCH = (154, 184, 204)
_ADDED     = (87,  168,  90)
_REMOVED   = (199,  80,  80)


def _rgba(rgb: tuple, a: float) -> str:
    return f"rgba({rgb[0]},{rgb[1]},{rgb[2]},{int(a * 255)})"


class _SectionHeader(QWidget):
    toggled = pyqtSignal(bool)  # True = expanded

    def __init__(self, label: str, count: int, rgb: tuple, parent=None):
        super().__init__(parent)
        self._expanded = True
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("section_header")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 10, 8, 2)
        layout.setSpacing(8)

        bar = QFrame()
        bar.setFixedWidth(3)
        bar.setMinimumHeight(12)
        bar.setStyleSheet(f"background:{_rgba(rgb, 1.0)}; border-radius:1px;")

        lbl = QLabel(f"{label}  ({count})")
        lbl.setStyleSheet(f"color:{_rgba(rgb, 1.0)}; font-weight:bold;")

        self._chevron = QLabel("▾")
        self._chevron.setStyleSheet(f"color:{_rgba(rgb, 0.55)}; font-size:13px;")

        layout.addWidget(bar, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch()
        layout.addWidget(self._chevron, 0, Qt.AlignmentFlag.AlignVCenter)

    def mousePressEvent(self, e) -> None:
        self._expanded = not self._expanded
        self._chevron.setText("▾" if self._expanded else "▸")
        self.toggled.emit(self._expanded)
        super().mousePressEvent(e)

    def enterEvent(self, e):
        wt = self.palette().color(QPalette.ColorRole.WindowText)
        self.setStyleSheet(
            f"QWidget#section_header {{ background:rgba({wt.red()},{wt.green()},{wt.blue()},12); border-radius:3px; }}"
        )

    def leaveEvent(self, e):
        self.setStyleSheet("")


class _Row(QWidget):
    clicked = pyqtSignal(str)  # package name

    def __init__(
        self,
        name: str,
        ver: str,
        size: str,
        rgb: tuple,
        bold: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._pkg = name

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 2, 12, 2)
        layout.setSpacing(4)

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color:{_rgba(rgb, 1.0)};" + (" font-weight:bold;" if bold else "")
        )

        ver_lbl = QLabel(ver)
        ver_lbl.setStyleSheet(f"color:{_rgba(rgb, 0.65)};")

        size_lbl = QLabel(size)
        size_lbl.setStyleSheet(f"color:{_rgba(rgb, 0.5)};")
        size_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(name_lbl, 3)
        layout.addWidget(ver_lbl, 4)
        layout.addWidget(size_lbl, 2)

        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def mousePressEvent(self, e) -> None:
        self.clicked.emit(self._pkg)
        super().mousePressEvent(e)

    def enterEvent(self, e):
        wt = self.palette().color(QPalette.ColorRole.WindowText)
        self.setStyleSheet(
            f"QWidget {{ background:rgba({wt.red()},{wt.green()},{wt.blue()},18);"
            " border-radius:3px; }"
        )

    def leaveEvent(self, e):
        self.setStyleSheet("")


class ChangelogWidget(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._inner = QWidget()
        self._vbox = QVBoxLayout(self._inner)
        self._vbox.setSpacing(0)
        self._vbox.setContentsMargins(0, 0, 0, 4)
        self._vbox.addStretch()
        self.setWidget(self._inner)

        self._rows: list[_Row] = []
        self._homepage_worker: HomepageWorker | None = None
        self.is_populated = False

    # ── public ──────────────────────────────────────────────────────────────

    def set_loading(self) -> None:
        self.is_populated = False
        self._clear()
        wt = self.palette().color(QPalette.ColorRole.WindowText)
        lbl = QLabel(_("Building closure, please wait…"))
        lbl.setStyleSheet(
            f"color:rgba({wt.red()},{wt.green()},{wt.blue()},120); padding:8px 8px;"
        )
        self._vbox.insertWidget(0, lbl)
        QTimer.singleShot(0, self._refresh_size)

    def populate(self, raw: str) -> None:
        self.is_populated = True
        self._clear()
        updated, added, removed = self._parse(raw) if raw.strip() else ([], [], [])

        if not updated and not added and not removed:
            wt = self.palette().color(QPalette.ColorRole.WindowText)
            lbl = QLabel(_("No package changes detected."))
            lbl.setStyleSheet(
                f"color:rgba({wt.red()},{wt.green()},{wt.blue()},120); padding:8px 8px;"
            )
            self._vbox.insertWidget(0, lbl)
        else:
            self._add_section(_("Updated"), updated, _UPD_MAJOR, level_colors=True)
            self._add_section(_("Added"),   added,   _ADDED)
            self._add_section(_("Removed"), removed, _REMOVED)
        QTimer.singleShot(0, self._refresh_size)

    # ── internals ───────────────────────────────────────────────────────────

    def _refresh_size(self) -> None:
        hint = self._inner.sizeHint().height()
        if hint > 4:
            self.setFixedHeight(hint)

    def _clear(self) -> None:
        self._rows.clear()
        while self._vbox.count() > 1:
            item = self._vbox.takeAt(0)
            if w := item.widget():
                w.deleteLater()

    def _add_section(
        self, label: str, items: list, rgb: tuple, level_colors: bool = False
    ) -> None:
        if not items:
            return
        insert_at = self._vbox.count() - 1

        header = _SectionHeader(label, len(items), rgb)
        self._vbox.insertWidget(insert_at, header)
        insert_at += 1

        section_rows: list[_Row] = []
        for name, old, new, size in items:
            if level_colors:
                lv  = self.bump_level(old, new)
                c   = {"major": _UPD_MAJOR, "minor": _UPD_MINOR, "patch": _UPD_PATCH}[lv]
                row = _Row(name, f"{old} → {new}", size, c, bold=(lv == "major"))
            else:
                ver = f"{old} → {new}" if old and new else (old or _("new"))
                row = _Row(name, ver, size, rgb)
            row.clicked.connect(self._fetch_homepage)
            section_rows.append(row)
            self._rows.append(row)
            self._vbox.insertWidget(insert_at, row)
            insert_at += 1

        def _on_toggle(expanded: bool) -> None:
            for r in section_rows:
                r.setVisible(expanded)
            QTimer.singleShot(0, self._refresh_size)

        header.toggled.connect(_on_toggle)

    # ── homepage on click ───────────────────────────────────────────────────

    def _fetch_homepage(self, name: str) -> None:
        if self._homepage_worker and self._homepage_worker.isRunning():
            return
        if self._homepage_worker:
            self._homepage_worker.finished.disconnect()
        self.setCursor(QCursor(Qt.CursorShape.WaitCursor))
        self._homepage_worker = HomepageWorker(name)
        self._homepage_worker.finished.connect(self._on_homepage)
        self._homepage_worker.start()

    def _on_homepage(self, url: str) -> None:
        self.unsetCursor()
        if url:
            QDesktopServices.openUrl(QUrl(url))

    # ── static helpers ──────────────────────────────────────────────────────

    @staticmethod
    def bump_level(old: str, new: str) -> str:
        def parts(v): return [int(x) for x in re.findall(r"\d+", v)]
        o, n = parts(old), parts(new)
        if not o or not n: return "minor"
        if o[0] != n[0]: return "major"
        if len(o) > 1 and len(n) > 1 and o[1] != n[1]: return "minor"
        return "patch"

    @staticmethod
    def _parse(raw: str):
        changed_re = re.compile(r"^(.+?):\s+(.+?)\s+→\s+(.+?)(?:,\s+(.+))?\s*$")
        added_re   = re.compile(r"^(.+?):\s+\(new\)(?:,\s+(.+))?\s*$")
        updated, added, removed = [], [], []
        for line in raw.strip().splitlines():
            line = line.strip()
            if not line: continue
            m = added_re.match(line)
            if m:
                added.append((m.group(1), "", "", m.group(2) or ""))
                continue
            m = changed_re.match(line)
            if m:
                name, old, new, size = m.group(1), m.group(2), m.group(3), m.group(4) or ""
                if "(gone)" in new:
                    removed.append((name, old, "", size))
                else:
                    updated.append((name, old, new, size))
        order = {"major": 0, "minor": 1, "patch": 2}
        updated.sort(key=lambda t: order[ChangelogWidget.bump_level(t[1], t[2])])
        return updated, added, removed
