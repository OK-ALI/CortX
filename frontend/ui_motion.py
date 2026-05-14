from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, QTimer
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QScrollBar, QWidget


MOTION_PRESETS = ("snappy", "balanced", "cinematic")


def profile_duration(
    profile: str,
    *,
    snappy: int,
    balanced: int,
    cinematic: int,
) -> int:
    if profile == "snappy":
        return snappy
    if profile == "cinematic":
        return cinematic
    return balanced


def adaptive_reveal_duration(chars: int, has_sources: bool = False, profile: str = "balanced") -> int:
    """Return reveal duration based on response length and motion profile."""
    safe_chars = max(int(chars), 0)

    if profile == "snappy":
        base = 250
        factor = 0.35
        clamp_min, clamp_max = 220, 900
    elif profile == "cinematic":
        base = 520
        factor = 0.75
        clamp_min, clamp_max = 450, 2000
    else:
        base = 380
        factor = 0.55
        clamp_min, clamp_max = 360, 1500

    duration = base + int(safe_chars * factor)
    if has_sources:
        duration += 120
    return max(clamp_min, min(duration, clamp_max))


def animate_widget_entrance(
    widget: QWidget,
    duration: int = 540,
    follow_scrollbar: QScrollBar | None = None,
) -> None:
    """Fade+expand a widget while optionally tracking scroll in parallel."""
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)

    widget.setMaximumHeight(0)

    opacity_anim = QPropertyAnimation(effect, b"opacity", widget)
    opacity_anim.setDuration(duration)
    opacity_anim.setStartValue(0.0)
    opacity_anim.setEndValue(1.0)
    opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    height_anim = QPropertyAnimation(widget, b"maximumHeight", widget)
    height_anim.setDuration(duration)
    height_anim.setStartValue(0)
    height_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    if follow_scrollbar is not None:
        def _follow_scroll(*_args) -> None:
            follow_scrollbar.setValue(follow_scrollbar.maximum())

        height_anim.valueChanged.connect(_follow_scroll)

    group = QParallelAnimationGroup(widget)
    group.addAnimation(opacity_anim)
    group.addAnimation(height_anim)

    def _finish() -> None:
        widget.setMaximumHeight(16777215)
        widget.setGraphicsEffect(None)
        if follow_scrollbar is not None:
            follow_scrollbar.setValue(follow_scrollbar.maximum())

    def _start() -> None:
        # Wait one event loop tick so size hints are stable.
        target_height = max(widget.sizeHint().height(), widget.minimumSizeHint().height(), 24)
        height_anim.setEndValue(target_height)
        group.start()

    group.finished.connect(_finish)
    QTimer.singleShot(0, _start)
    widget._entrance_anim = group  # type: ignore[attr-defined]


def animate_widget_exit(
    widget: QWidget,
    duration: int = 180,
    on_finished: Callable[[], None] | None = None,
) -> None:
    """Fade+collapse widget and optionally invoke callback when complete."""
    current_height = max(widget.height(), widget.sizeHint().height(), 24)
    widget.setMaximumHeight(current_height)

    existing = widget.graphicsEffect()
    effect = existing if isinstance(existing, QGraphicsOpacityEffect) else QGraphicsOpacityEffect(widget)
    if existing is None:
        widget.setGraphicsEffect(effect)
    effect.setOpacity(1.0)

    opacity_anim = QPropertyAnimation(effect, b"opacity", widget)
    opacity_anim.setDuration(duration)
    opacity_anim.setStartValue(1.0)
    opacity_anim.setEndValue(0.0)
    opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    height_anim = QPropertyAnimation(widget, b"maximumHeight", widget)
    height_anim.setDuration(duration)
    height_anim.setStartValue(current_height)
    height_anim.setEndValue(0)
    height_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    group = QParallelAnimationGroup(widget)
    group.addAnimation(opacity_anim)
    group.addAnimation(height_anim)

    def _done() -> None:
        if on_finished is not None:
            on_finished()

    group.finished.connect(_done)
    group.start()
    widget._exit_anim = group  # type: ignore[attr-defined]


def animate_opacity_pulse(widget: QWidget, duration: int = 240) -> None:
    """Quick opacity pulse for selection emphasis."""
    existing = widget.graphicsEffect()
    effect = existing if isinstance(existing, QGraphicsOpacityEffect) else QGraphicsOpacityEffect(widget)
    if existing is None:
        widget.setGraphicsEffect(effect)
    effect.setOpacity(1.0)

    fade_out = QPropertyAnimation(effect, b"opacity", widget)
    fade_out.setDuration(max(80, duration // 2))
    fade_out.setStartValue(1.0)
    fade_out.setEndValue(0.78)
    fade_out.setEasingCurve(QEasingCurve.Type.InOutQuad)

    fade_in = QPropertyAnimation(effect, b"opacity", widget)
    fade_in.setDuration(max(80, duration // 2))
    fade_in.setStartValue(0.78)
    fade_in.setEndValue(1.0)
    fade_in.setEasingCurve(QEasingCurve.Type.InOutQuad)

    def _run_fade_in() -> None:
        fade_in.start()

    fade_out.finished.connect(_run_fade_in)
    fade_out.start()
    widget._pulse_anim_out = fade_out  # type: ignore[attr-defined]
    widget._pulse_anim_in = fade_in  # type: ignore[attr-defined]


def animate_scrollbar_to(scrollbar: QScrollBar, target: int, duration: int = 220) -> None:
    """Smoothly animate vertical scroll to target value."""
    start = scrollbar.value()
    if abs(start - target) < 4:
        scrollbar.setValue(target)
        return

    anim = QPropertyAnimation(scrollbar, b"value", scrollbar)
    anim.setDuration(duration)
    anim.setStartValue(start)
    anim.setEndValue(target)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start()
    scrollbar._scroll_anim = anim  # type: ignore[attr-defined]
