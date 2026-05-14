"""Reusable animated glow effect for PyQt6 widgets."""
from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PyQt6.QtGui import QColor, QEnterEvent
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QWidget


class GlowEffect:
    """Attach a hover-triggered glow animation to any QWidget."""

    def __init__(
        self,
        widget: QWidget,
        color: str = "#1CA7EC",
        radius_start: float = 0.0,
        radius_end: float = 18.0,
        duration: int = 250,
    ) -> None:
        self.widget = widget
        self.color = QColor(color)
        self.radius_start = radius_start
        self.radius_end = radius_end
        self.duration = duration

        # Create shadow effect
        self.effect = QGraphicsDropShadowEffect(widget)
        self.effect.setOffset(0, 0)
        self.effect.setBlurRadius(radius_start)
        self.effect.setColor(self.color)
        widget.setGraphicsEffect(self.effect)

        # Animation
        self._anim = QPropertyAnimation(self.effect, b"blurRadius", widget)
        self._anim.setDuration(duration)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        # Monkey-patch enter/leave events
        original_enter = widget.enterEvent
        original_leave = widget.leaveEvent

        def _enter(event: QEnterEvent | None) -> None:
            self._animate(self.radius_end)
            if original_enter:
                original_enter(event)

        def _leave(event: QEnterEvent | None) -> None:
            self._animate(self.radius_start)
            if original_leave:
                original_leave(event)

        widget.enterEvent = _enter  # type: ignore[assignment]
        widget.leaveEvent = _leave  # type: ignore[assignment]

    def _animate(self, target: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self.effect.blurRadius())
        self._anim.setEndValue(target)
        self._anim.start()


def apply_glow(
    widget: QWidget,
    color: str = "#1CA7EC",
    radius: float = 18.0,
    duration: int = 250,
) -> GlowEffect:
    """Convenience function to add hover glow to a widget."""
    return GlowEffect(widget, color=color, radius_end=radius, duration=duration)
