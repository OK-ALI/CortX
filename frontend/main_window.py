from __future__ import annotations

import asyncio
import json
from pathlib import Path
import re
from typing import TYPE_CHECKING

from PyQt6.QtCore import QSettings, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
	QFileDialog,
	QHBoxLayout,
	QMainWindow,
	QMessageBox,
	QPushButton,
	QSplitter,
	QVBoxLayout,
	QWidget,
)

from frontend.chat_widget import ChatWidget
from frontend.glow_effect import apply_glow
from frontend.input_bar import InputBar
from frontend.response_formatter import format_chat_answer, format_sources
from frontend.sidebar import Sidebar
from database.lance_store import LanceStore

if TYPE_CHECKING:
	from backend.ai.pipeline import CortxPipeline


class QueryWorker(QThread):
	answered = pyqtSignal(str, list)
	failed = pyqtSignal(str)
	status_update = pyqtSignal(str)

	def __init__(
		self,
		pipeline: CortxPipeline,
		query: str,
		history_messages: list[dict] | None = None,
		explicit_context: dict | None = None,
		parent: QWidget | None = None,
	) -> None:
		super().__init__(parent)
		self.pipeline = pipeline
		self.query = query
		self.history_messages = history_messages or []
		self.explicit_context = explicit_context

	def run(self) -> None:
		try:
			original_callback = self.pipeline.status_callback
			self.pipeline.status_callback = lambda msg: self.status_update.emit(msg)
			result = asyncio.run(
				self.pipeline.run(
					self.query,
					conversation_messages=self.history_messages,
					explicit_context=self.explicit_context,
				)
			)
			self.pipeline.status_callback = original_callback
			answer = format_chat_answer(result.answer)
			sources = format_sources(result.sources)
			self.answered.emit(answer, sources)
		except Exception as exc:
			self.failed.emit(str(exc))


class MainWindow(QMainWindow):
	def __init__(self, pipeline: CortxPipeline, parent: QWidget | None = None) -> None:
		super().__init__(parent)
		self.pipeline = pipeline
		self._worker: QueryWorker | None = None
		self._settings = QSettings("Cortx", "Desktop")
		self._theme = str(self._settings.value("theme", "dark"))
		self._motion_profile = "cinematic"
		self._store = LanceStore()
		self._current_conversation_id: str | None = None
		self._shortcuts: list[QShortcut] = []

		self.setWindowTitle("CortX")
		icon_path = Path(__file__).parent.parent / "assets" / "icon.png"
		if icon_path.exists():
			self.setWindowIcon(QIcon(str(icon_path)))
			
		self.resize(1340, 860)
		self.setMinimumSize(900, 600)

		self._build_ui()
		self._bind_signals()
		self._install_shortcuts()
		self._apply_glow_effects()
		self._apply_theme(self._theme)
		self._load_conversations()

	def _build_ui(self) -> None:
		root = QWidget(self)
		root.setObjectName("RootContainer")
		root_layout = QHBoxLayout(root)
		root_layout.setContentsMargins(0, 0, 0, 0)
		root_layout.setSpacing(0)

		self.root_splitter = QSplitter(Qt.Orientation.Horizontal, root)
		self.root_splitter.setObjectName("RootSplitter")
		self.root_splitter.setHandleWidth(6)
		self.root_splitter.setChildrenCollapsible(True)

		# Sidebar
		self.sidebar = Sidebar(self.root_splitter)

		# Chat area
		chat_area = QWidget(self.root_splitter)
		chat_area.setObjectName("ChatArea")
		chat_layout = QVBoxLayout(chat_area)
		chat_layout.setContentsMargins(0, 0, 0, 0)
		chat_layout.setSpacing(0)

		# Top bar with sidebar toggle
		top_bar = QWidget(chat_area)
		top_bar.setObjectName("ChatTopBar")
		top_bar_layout = QHBoxLayout(top_bar)
		top_bar_layout.setContentsMargins(12, 8, 12, 8)
		top_bar_layout.setSpacing(8)

		self.sidebar_toggle = QPushButton("☰", top_bar)
		self.sidebar_toggle.setObjectName("SidebarToggle")
		self.sidebar_toggle.setFixedSize(36, 36)
		self.sidebar_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
		self.sidebar_toggle.clicked.connect(self._on_sidebar_toggle)
		self.sidebar_toggle.setToolTip("Toggle sidebar (Ctrl+B)")
		top_bar_layout.addWidget(self.sidebar_toggle)

		self.export_btn = QPushButton("Export", top_bar)
		self.export_btn.setObjectName("ExportChatBtn")
		self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
		self.export_btn.setMinimumHeight(36)
		self.export_btn.clicked.connect(self._on_export_chat)
		self.export_btn.setToolTip("Export conversation (Ctrl+E)")
		top_bar_layout.addWidget(self.export_btn)

		top_bar_layout.addStretch(1)

		chat_layout.addWidget(top_bar)
		self.chat_widget = ChatWidget(chat_area)
		self.chat_widget.set_motion_profile("cinematic")
		self.input_bar = InputBar(chat_area)

		chat_layout.addWidget(self.chat_widget, 1)
		chat_layout.addWidget(self.input_bar)

		self.root_splitter.addWidget(self.sidebar)
		self.root_splitter.addWidget(chat_area)
		self.root_splitter.setStretchFactor(0, 0)
		self.root_splitter.setStretchFactor(1, 1)
		self.root_splitter.setSizes([self.sidebar.expanded_width, 1000])
		self.root_splitter.splitterMoved.connect(self._on_splitter_moved)

		handle = self.root_splitter.handle(1)
		handle.setCursor(Qt.CursorShape.SplitHCursor)

		root_layout.addWidget(self.root_splitter, 1)
		self.setCentralWidget(root)

	def _bind_signals(self) -> None:
		self.sidebar.new_chat_requested.connect(self._on_new_chat)
		self.sidebar.chat_selected.connect(self._on_chat_selected)
		self.sidebar.chat_renamed.connect(self._on_chat_renamed)
		self.sidebar.chat_deleted.connect(self._on_chat_deleted)
		self.sidebar.theme_toggled.connect(self._on_theme_toggled)
		self.chat_widget.context_action_requested.connect(self._on_context_action_requested)
		self.chat_widget.selected_text_action_requested.connect(self._on_selected_text_action_requested)
		self.input_bar.context_jump_requested.connect(self._on_context_jump_requested)
		self.input_bar.submit_requested.connect(self._on_submit_query)

	def _install_shortcuts(self) -> None:
		shortcut_new = QShortcut(QKeySequence("Ctrl+N"), self)
		shortcut_new.activated.connect(self._on_new_chat)

		shortcut_sidebar = QShortcut(QKeySequence("Ctrl+B"), self)
		shortcut_sidebar.activated.connect(self._on_sidebar_toggle)

		shortcut_export = QShortcut(QKeySequence("Ctrl+E"), self)
		shortcut_export.activated.connect(self._on_export_chat)

		shortcut_focus_input = QShortcut(QKeySequence("Ctrl+L"), self)
		shortcut_focus_input.activated.connect(lambda: self.input_bar.editor.setFocus())

		self._shortcuts = [
			shortcut_new,
			shortcut_sidebar,
			shortcut_export,
			shortcut_focus_input,
		]

	def _apply_glow_effects(self) -> None:
		"""Attach animated glow effects to interactive elements."""
		apply_glow(self.sidebar.new_chat_btn, color="#1CA7EC", radius=16, duration=300)
		apply_glow(self.sidebar_toggle, color="#1CA7EC", radius=12, duration=200)
		apply_glow(self.export_btn, color="#1CA7EC", radius=10, duration=180)

	# ------------------------------------------------------------------
	# Sidebar
	# ------------------------------------------------------------------

	def _on_sidebar_toggle(self) -> None:
		was_expanded = self.sidebar.is_expanded
		self.sidebar.toggle()

		total_width = max(self.root_splitter.width(), 2)
		if was_expanded:
			self.root_splitter.setSizes([0, total_width])
		else:
			target = self.sidebar.expanded_width
			target = min(target, max(total_width - 200, 120))
			self.root_splitter.setSizes([target, max(total_width - target, 1)])

	def _on_splitter_moved(self, pos: int, index: int) -> None:
		_ = (pos, index)
		self.sidebar.update_from_splitter_width(self.sidebar.width())

	def _load_conversations(self) -> None:
		conversations = self._store.list_conversations()
		self.sidebar.load_conversations(conversations)

	def _on_new_chat(self) -> None:
		cid = self._store.create_conversation("New Chat")
		self.sidebar.add_conversation(cid, "New Chat")
		self._switch_to_conversation(cid)

	def _on_chat_selected(self, conversation_id: str) -> None:
		self._switch_to_conversation(conversation_id)

	def _on_chat_renamed(self, conversation_id: str, new_title: str) -> None:
		self._store.rename_conversation(conversation_id, new_title)
		self.sidebar.update_title(conversation_id, new_title)

	def _on_chat_deleted(self, conversation_id: str) -> None:
		title = (self.sidebar.get_title(conversation_id) or "This chat").strip()
		if len(title) > 70:
			title = f"{title[:67]}..."
		confirm = QMessageBox.question(
			self,
			"Delete Chat",
			f'Delete "{title}" permanently?\n\nThis action cannot be undone.',
			QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
			QMessageBox.StandardButton.No,
		)
		if confirm != QMessageBox.StandardButton.Yes:
			return

		self._store.delete_conversation(conversation_id)
		self.sidebar.remove_conversation(conversation_id)
		if self._current_conversation_id == conversation_id:
			self._current_conversation_id = None
			self.chat_widget.clear_chat()

	def _switch_to_conversation(self, conversation_id: str) -> None:
		self._current_conversation_id = conversation_id
		self.sidebar.set_active(conversation_id)
		messages = self._store.get_messages(conversation_id)
		self.chat_widget.load_messages(messages)

	# ------------------------------------------------------------------
	# Query handling
	# ------------------------------------------------------------------

	def _on_submit_query(self, query: str) -> None:
		if self._worker is not None and self._worker.isRunning():
			return

		if self._current_conversation_id is None:
			self._on_new_chat()

		conversation_history = self._store.get_messages(self._current_conversation_id)
		if not conversation_history:
			title = query[:50].strip()
			if len(query) > 50:
				title += "..."
			self._store.rename_conversation(self._current_conversation_id, title)
			self.sidebar.update_title(self._current_conversation_id, title)

		context_snapshot = self.input_bar.get_context_snapshot()
		history_for_resolution = self._context_history_for_resolution(
			conversation_history,
			context_snapshot,
		)
		user_message_id = self._store.add_message(self._current_conversation_id, "user", query)
		self.chat_widget.add_user_message(
			query,
			context_id=user_message_id,
			context_hint=context_snapshot,
		)
		self.input_bar.clear()
		self.input_bar.set_busy(True)

		self._worker = QueryWorker(
			self.pipeline,
			query,
			history_messages=history_for_resolution,
			explicit_context=context_snapshot,
			parent=self,
		)
		self._worker.answered.connect(self._on_answer_ready)
		self._worker.failed.connect(self._on_query_failed)
		self._worker.finished.connect(self._on_worker_finished)
		self._worker.status_update.connect(self._on_status_update)
		self._worker.start()

	def _context_history_for_resolution(
		self,
		conversation_history: list[dict],
		context_snapshot: dict | None,
	) -> list[dict] | None:
		"""Return a scoped history only when user explicitly selected context."""
		if not context_snapshot:
			return None

		if not conversation_history:
			return None

		target_id = str(context_snapshot.get("target_id", "")).strip()
		if not target_id:
			return conversation_history[-4:]

		target_index = next(
			(i for i, item in enumerate(conversation_history) if str(item.get("id", "")).strip() == target_id),
			-1,
		)
		if target_index < 0:
			return conversation_history[-4:]

		start = max(target_index - 2, 0)
		end = min(target_index + 3, len(conversation_history))
		return conversation_history[start:end]

	def _on_status_update(self, message: str) -> None:
		self.chat_widget.set_status(message)

	def _on_answer_ready(self, answer: str, sources: list) -> None:
		assistant_message_id: str | None = None
		if self._current_conversation_id:
			assistant_message_id = self._store.add_message(
				self._current_conversation_id, "assistant", answer, sources=sources
			)
		self.chat_widget.add_assistant_message(
			answer,
			sources=sources if sources else None,
			context_id=assistant_message_id,
		)

	def _on_query_failed(self, error: str) -> None:
		self.chat_widget.add_assistant_message(f"**Request failed:** {error}")

	def _on_worker_finished(self) -> None:
		self.input_bar.set_busy(False)
		self._worker = None

	def _short_context(self, text: str, limit: int = 260) -> str:
		compact = " ".join(text.split()).strip()
		if len(compact) <= limit:
			return compact
		return f"{compact[:limit - 3]}..."

	def _on_context_action_requested(self, action: str, context_text: str, context_id: str) -> None:
		snippet = self._short_context(context_text)
		if action == "reply":
			prompt = "My follow-up question: "
		elif action == "follow":
			prompt = "Focus on: "
		elif action == "update":
			prompt = "Check latest updates on: "
		else:
			prompt = ""
		self.input_bar.set_context_hint(action, snippet, context_id=context_id or None)
		self.input_bar.set_prefill(prompt, muted=True)

	def _on_selected_text_action_requested(self, action: str, selected_text: str) -> None:
		snippet = self._short_context(selected_text)
		if action == "ask":
			prompt = "Question: "
		elif action == "explain":
			prompt = "Please explain this: "
		elif action == "update":
			prompt = "Find latest updates on: "
		else:
			prompt = ""
		self.input_bar.set_context_hint(action, snippet, context_id=None)
		self.input_bar.set_prefill(prompt, muted=True)

	def _on_context_jump_requested(self, context_id: str) -> None:
		self.chat_widget.focus_message(context_id)

	def _on_export_chat(self) -> None:
		if self._current_conversation_id is None:
			QMessageBox.information(self, "Export", "Start a conversation before exporting.")
			return

		messages = self._store.get_messages(self._current_conversation_id)
		if not messages:
			QMessageBox.information(self, "Export", "This conversation has no messages to export.")
			return

		title = self.sidebar.get_title(self._current_conversation_id) or "Conversation"
		safe_title = re.sub(r"[^A-Za-z0-9 _-]+", "", title).strip().replace(" ", "_") or "conversation"

		default_dir = Path.home() / "Documents"
		default_path = str(default_dir / f"{safe_title}.md")
		filters = "Markdown (*.md);;JSON (*.json);;Text (*.txt)"
		file_path, chosen_filter = QFileDialog.getSaveFileName(self, "Export Conversation", default_path, filters)
		if not file_path:
			return

		path = Path(file_path)
		if not path.suffix:
			if "JSON" in chosen_filter:
				path = path.with_suffix(".json")
			elif "Text" in chosen_filter:
				path = path.with_suffix(".txt")
			else:
				path = path.with_suffix(".md")

		if path.suffix.lower() == ".json":
			payload = {
				"conversation_id": self._current_conversation_id,
				"title": title,
				"message_count": len(messages),
				"messages": messages,
			}
			path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
		elif path.suffix.lower() == ".txt":
			path.write_text(self._build_plain_text_export(title, messages), encoding="utf-8")
		else:
			path.write_text(self._build_markdown_export(title, messages), encoding="utf-8")

		QMessageBox.information(self, "Export", f"Conversation exported to:\n{path}")

	def _build_markdown_export(self, title: str, messages: list[dict]) -> str:
		lines = [f"# {title}", ""]
		for message in messages:
			role = str(message.get("role", "user")).strip().capitalize()
			created_at = str(message.get("created_at", "")).strip()
			content = str(message.get("content", "")).strip()
			lines.append(f"## {role}")
			if created_at:
				lines.append(f"_Time: {created_at}_")
				lines.append("")
			lines.append(content or "(empty)")
			sources = message.get("sources", []) or []
			if sources:
				lines.append("")
				lines.append("Sources:")
				for source in sources:
					lines.append(f"- {source}")
			lines.append("")
		return "\n".join(lines).strip() + "\n"

	def _build_plain_text_export(self, title: str, messages: list[dict]) -> str:
		lines = [title, "=" * len(title), ""]
		for message in messages:
			role = str(message.get("role", "user")).strip().upper()
			created_at = str(message.get("created_at", "")).strip()
			content = str(message.get("content", "")).strip()
			header = f"[{role}]"
			if created_at:
				header += f" ({created_at})"
			lines.append(header)
			lines.append(content or "(empty)")
			sources = message.get("sources", []) or []
			if sources:
				lines.append("Sources:")
				for source in sources:
					lines.append(f"  - {source}")
			lines.append("")
		return "\n".join(lines).strip() + "\n"

	# ------------------------------------------------------------------
	# Theme
	# ------------------------------------------------------------------

	def _on_theme_toggled(self, is_light: bool) -> None:
		self._apply_theme("light" if is_light else "dark")

	def _apply_theme(self, theme: str) -> None:
		styles_dir = Path(__file__).resolve().parent / "styles"
		stylesheet_path = styles_dir / f"{theme}_theme.qss"
		if not stylesheet_path.exists():
			return
		self.setStyleSheet(stylesheet_path.read_text(encoding="utf-8"))
		self._theme = theme
		self._settings.setValue("theme", theme)
		self.sidebar.theme_switch.blockSignals(True)
		self.sidebar.theme_switch.setChecked(theme == "light")
		self.sidebar.theme_switch.blockSignals(False)
		self.sidebar.theme_switch.sync_position()

	def closeEvent(self, event) -> None:
		if self._worker is not None and self._worker.isRunning():
			self._worker.requestInterruption()
			self._worker.wait(2000)
		super().closeEvent(event)
