from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, pyqtProperty
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QAbstractButton, QWidget


class ThemeSwitch(QAbstractButton):
    """Small iOS-style animated switch for theme toggling."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self.setFixedSize(54, 32)

        self._thumb_margin = 4.0
        self._thumb_size = 24.0
        self._icon_scale = 0.58
        self._offset = self._thumb_margin

        assets_dir = Path(__file__).resolve().parent.parent / "assets"
        self._light_icon = self._load_first_icon(assets_dir, ["theme_light.png", "toggle_light.png", "sun.png"])
        self._dark_icon = self._load_first_icon(assets_dir, ["theme_dark.png", "toggle_dark.png", "moon.png"])

        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(170)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.toggled.connect(self._on_toggled)

    def sizeHint(self) -> QSize:  # noqa: D401
        return QSize(54, 32)

    def _on_toggled(self, checked: bool) -> None:
        self._anim.stop()
        end = self.width() - self._thumb_size - self._thumb_margin if checked else self._thumb_margin
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(end)
        self._anim.start()

    def sync_position(self) -> None:
        self._anim.stop()
        self._offset = self.width() - self._thumb_size - self._thumb_margin if self.isChecked() else self._thumb_margin
        self.update()

    def _load_first_icon(self, assets_dir: Path, names: list[str]) -> QPixmap:
        for name in names:
            path = assets_dir / name
            if path.exists():
                pixmap = QPixmap(str(path))
                if not pixmap.isNull():
                    return pixmap
        return QPixmap()

    def get_offset(self) -> float:
        return self._offset

    def set_offset(self, value: float) -> None:
        self._offset = float(value)
        self.update()

    offset = pyqtProperty(float, get_offset, set_offset)

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        if self.isChecked():
            track = QColor("#19C37D")
        else:
            track = QColor("#A7B4C2")

        painter.setBrush(track)
        radius = (self.height() - 2) / 2
        painter.drawRoundedRect(1, 1, self.width() - 2, self.height() - 2, radius, radius)

        painter.setBrush(QColor("#FFFFFF"))
        thumb_y = int((self.height() - self._thumb_size) / 2)
        painter.drawEllipse(int(self._offset), thumb_y, int(self._thumb_size), int(self._thumb_size))
        self._paint_thumb_icon(painter, thumb_y)

    def _paint_thumb_icon(self, painter: QPainter, thumb_y: int) -> None:
        icon_size = max(12, int(self._thumb_size * self._icon_scale))
        thumb_x = int(self._offset)
        icon_x = thumb_x + int((self._thumb_size - icon_size) / 2)
        icon_y = thumb_y + int((self._thumb_size - icon_size) / 2)

        pixmap = self._light_icon if self.isChecked() else self._dark_icon
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                icon_size,
                icon_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            draw_x = icon_x + int((icon_size - scaled.width()) / 2)
            draw_y = icon_y + int((icon_size - scaled.height()) / 2)
            painter.drawPixmap(draw_x, draw_y, scaled)
            return

        self._draw_fallback_icon(painter, icon_x, icon_y, icon_size)

    def _draw_fallback_icon(self, painter: QPainter, x: int, y: int, size: int) -> None:
        cx = x + size / 2
        cy = y + size / 2
        radius = max(3.0, size * 0.24)

        if self.isChecked():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#F6C343"))
            painter.drawEllipse(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2))

            ray_pen = QPen(QColor("#F6C343"))
            ray_pen.setWidth(2)
            painter.setPen(ray_pen)
            ray = radius + 2
            outer = ray + 3
            painter.drawLine(int(cx), int(cy - outer), int(cx), int(cy - ray))
            painter.drawLine(int(cx), int(cy + ray), int(cx), int(cy + outer))
            painter.drawLine(int(cx - outer), int(cy), int(cx - ray), int(cy))
            painter.drawLine(int(cx + ray), int(cy), int(cx + outer), int(cy))
            return

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#5B6672"))
        painter.drawEllipse(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2))
        painter.setBrush(QColor("#FFFFFF"))
        cut = radius * 0.85
        painter.drawEllipse(int(cx - radius + cut), int(cy - radius), int(radius * 2), int(radius * 2))
