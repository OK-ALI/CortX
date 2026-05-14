from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, Qt, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QMouseEvent, QTextCursor
from PyQt6.QtWidgets import (
	QGraphicsOpacityEffect,
	QHBoxLayout,
	QPushButton,
	QSizePolicy,
	QTextEdit,
	QVBoxLayout,
	QWidget,
)

from frontend.elided_label import ElidedLabel
from frontend.glow_effect import apply_glow


class _ComposerTextEdit(QTextEdit):
	submitted = pyqtSignal()

	def __init__(self, parent: QWidget | None = None) -> None:
		super().__init__(parent)
		self._anim_height = 44

	def keyPressEvent(self, event: QKeyEvent) -> None:
		if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
			if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
				event.accept()
				self.submitted.emit()
				return
		super().keyPressEvent(event)

	def _get_anim_height(self) -> int:
		return int(self._anim_height)

	def _set_anim_height(self, value: int) -> None:
		height = max(44, min(int(value), 300))
		self._anim_height = height
		self.setFixedHeight(height)

	animHeight = pyqtProperty(int, _get_anim_height, _set_anim_height)


class _ContextStrip(QWidget):
	clicked = pyqtSignal()

	def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
		if event.button() == Qt.MouseButton.LeftButton:
			self.clicked.emit()
		super().mousePressEvent(event)


class InputBar(QWidget):
	submit_requested = pyqtSignal(str)
	context_jump_requested = pyqtSignal(str)

	def __init__(self, parent: QWidget | None = None) -> None:
		super().__init__(parent)
		self.setObjectName("InputBar")

		layout = QHBoxLayout(self)
		layout.setContentsMargins(40, 8, 40, 14)
		layout.setSpacing(0)

		# Container frame for the input area
		self.container = QWidget(self)
		self.container.setObjectName("InputContainer")
		container_layout = QVBoxLayout(self.container)
		container_layout.setContentsMargins(14, 8, 6, 6)
		container_layout.setSpacing(6)

		self.context_strip = _ContextStrip(self.container)
		self.context_strip.setObjectName("InputContextStrip")
		strip_layout = QHBoxLayout(self.context_strip)
		strip_layout.setContentsMargins(8, 4, 8, 4)
		strip_layout.setSpacing(8)

		self.context_mode = ElidedLabel("Reply", self.context_strip)
		self.context_mode.setObjectName("InputContextMode")
		strip_layout.addWidget(self.context_mode, 0)

		self.context_preview = ElidedLabel("", self.context_strip)
		self.context_preview.setObjectName("InputContextPreview")
		self.context_preview.setWordWrap(False)
		self.context_preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
		strip_layout.addWidget(self.context_preview, 1)

		self.context_clear = QPushButton("✕", self.context_strip)
		self.context_clear.setObjectName("InputContextClear")
		self.context_clear.setCursor(Qt.CursorShape.PointingHandCursor)
		self.context_clear.setFixedSize(20, 20)
		self.context_clear.clicked.connect(self.clear_context_hint)
		strip_layout.addWidget(self.context_clear, 0)

		self._context_opacity_effect = QGraphicsOpacityEffect(self.context_strip)
		self._context_opacity_effect.setOpacity(0.0)
		self.context_strip.setGraphicsEffect(self._context_opacity_effect)
		self._context_anim_group: QParallelAnimationGroup | None = None
		self._context_strip_target_height = 30

		self.context_strip.setVisible(False)
		self.context_strip.setMaximumHeight(0)
		self.context_strip.setProperty("hasTarget", False)
		self._context_target_id: str | None = None
		self._context_action: str | None = None
		self.context_strip.clicked.connect(self._on_context_strip_clicked)
		container_layout.addWidget(self.context_strip)

		composer_row = QWidget(self.container)
		composer_layout = QHBoxLayout(composer_row)
		composer_layout.setContentsMargins(2, 0, 0, 0)
		composer_layout.setSpacing(8)

		self.editor = _ComposerTextEdit(self.container)
		self.editor.setObjectName("Composer")
		self.editor.setProperty("contextPrefill", False)
		self.editor.setPlaceholderText("Ask anything...")
		self.editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
		self.editor.setAcceptRichText(False)
		self.editor.setMinimumHeight(44)
		self.editor.setMaximumHeight(300)
		self.editor.setFixedHeight(44)
		self.editor.textChanged.connect(self._autosize_editor)
		self.editor.submitted.connect(self._on_submit)
		self._editor_height_anim = QPropertyAnimation(self.editor, b"animHeight", self)
		self._editor_height_anim.setDuration(130)
		self._editor_height_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
		composer_layout.addWidget(self.editor)

		self.send_button = QPushButton("➤", self.container)
		self.send_button.setObjectName("SendButton")
		self.send_button.clicked.connect(self._on_submit)
		self.send_button.setFixedSize(40, 40)
		self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
		composer_layout.addWidget(self.send_button, 0, Qt.AlignmentFlag.AlignBottom)

		container_layout.addWidget(composer_row)

		layout.addWidget(self.container)

		# Animated glow effects
		self._container_glow = apply_glow(self.container, color="#1CA7EC", radius=20, duration=300)
		self._send_glow = apply_glow(self.send_button, color="#2CC4FF", radius=14, duration=200)

	def set_busy(self, busy: bool) -> None:
		self.editor.setDisabled(busy)
		self.send_button.setDisabled(busy)

	def clear(self) -> None:
		self.editor.clear()
		self.clear_context_hint()
		self._autosize_editor()

	def set_prefill(self, text: str, muted: bool = False) -> None:
		self.editor.setProperty("contextPrefill", bool(muted))
		self._refresh_editor_style()
		self.editor.setPlainText(text)
		cursor = self.editor.textCursor()
		cursor.movePosition(QTextCursor.MoveOperation.End)
		self.editor.setTextCursor(cursor)
		self._autosize_editor()
		self.editor.setFocus()

	def set_context_hint(self, action: str, context: str, context_id: str | None = None) -> None:
		labels = {
			"reply": "Replying to",
			"follow": "Following",
			"update": "Update on",
			"ask": "Asking about",
			"explain": "Explaining",
		}
		self.context_mode.setText(labels.get(action, "Context"))
		self.context_preview.setText(context)
		self._context_action = action
		self._context_target_id = context_id
		self.context_strip.setProperty("hasTarget", bool(context_id))
		if context_id:
			self.context_strip.setCursor(Qt.CursorShape.PointingHandCursor)
		else:
			self.context_strip.setCursor(Qt.CursorShape.ArrowCursor)
		self._refresh_context_strip_style()
		self._animate_context_strip(show=True)

	def clear_context_hint(self) -> None:
		self.context_preview.setText("")
		self._context_action = None
		self._context_target_id = None
		self.context_strip.setProperty("hasTarget", False)
		self.context_strip.setCursor(Qt.CursorShape.ArrowCursor)
		self._refresh_context_strip_style()
		self.editor.setProperty("contextPrefill", False)
		self._refresh_editor_style()
		self._animate_context_strip(show=False)

	def _on_context_strip_clicked(self) -> None:
		if self._context_target_id:
			self.context_jump_requested.emit(self._context_target_id)

	def get_context_snapshot(self) -> dict | None:
		if not self.context_strip.isVisible():
			return None
		return {
			"action": self._context_action or "context",
			"label": self.context_mode.full_text(),
			"preview": self.context_preview.full_text(),
			"target_id": self._context_target_id,
		}

	def _refresh_editor_style(self) -> None:
		self.editor.style().unpolish(self.editor)
		self.editor.style().polish(self.editor)
		self.editor.update()

	def _refresh_context_strip_style(self) -> None:
		self.context_strip.style().unpolish(self.context_strip)
		self.context_strip.style().polish(self.context_strip)
		self.context_strip.update()

	def _autosize_editor(self) -> None:
		doc_height = int(self.editor.document().size().height())
		new_height = min(max(44, doc_height + 12), 300)
		if self.editor.height() == new_height:
			return
		self._editor_height_anim.stop()
		self._editor_height_anim.setStartValue(self.editor.height())
		self._editor_height_anim.setEndValue(new_height)
		self._editor_height_anim.start()

	def _animate_context_strip(self, show: bool) -> None:
		target_height = self._context_strip_target_height
		if self._context_anim_group is not None and self._context_anim_group.state():
			self._context_anim_group.stop()

		if show:
			self.context_strip.setVisible(True)

		opacity_anim = QPropertyAnimation(self._context_opacity_effect, b"opacity", self)
		height_anim = QPropertyAnimation(self.context_strip, b"maximumHeight", self)
		duration = 170 if show else 130
		for anim in (opacity_anim, height_anim):
			anim.setDuration(duration)
			anim.setEasingCurve(QEasingCurve.Type.OutCubic)

		opacity_anim.setStartValue(self._context_opacity_effect.opacity())
		opacity_anim.setEndValue(1.0 if show else 0.0)
		height_anim.setStartValue(self.context_strip.maximumHeight())
		height_anim.setEndValue(target_height if show else 0)

		group = QParallelAnimationGroup(self)
		group.addAnimation(opacity_anim)
		group.addAnimation(height_anim)

		def _on_finished() -> None:
			if not show:
				self.context_strip.setVisible(False)

		group.finished.connect(_on_finished)
		group.start()
		self._context_anim_group = group

	def _on_submit(self) -> None:
		text = self.editor.toPlainText().strip()
		if not text:
			return
		self.submit_requested.emit(text)
