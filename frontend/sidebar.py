"""Left sidebar with chat history, new chat button, theme toggle, and collapse."""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from frontend.theme_switch import ThemeSwitch
from frontend.ui_motion import animate_opacity_pulse, animate_widget_entrance


SIDEBAR_EXPANDED_WIDTH = 260
SIDEBAR_COLLAPSED_WIDTH = 0
SIDEBAR_MIN_RESTORE_WIDTH = 180
SIDEBAR_MAX_WIDTH = 460


# ---------------------------------------------------------------------------
# Individual chat item in the sidebar
# ---------------------------------------------------------------------------

class ChatItem(QFrame):
    """One conversation entry in the sidebar list."""

    clicked = pyqtSignal(str)
    rename_requested = pyqtSignal(str, str)
    delete_requested = pyqtSignal(str)

    def __init__(
        self,
        conversation_id: str,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.conversation_id = conversation_id
        self.setObjectName("ChatItem")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 6, 0)
        layout.setSpacing(4)

        self.title_label = QLabel("", self)
        self.title_label.setObjectName("ChatItemTitle")
        self.title_label.setWordWrap(False)
        layout.addWidget(self.title_label, 1)

        self.title_editor = QLineEdit(self)
        self.title_editor.setObjectName("ChatItemEditor")
        self.title_editor.setVisible(False)
        self.title_editor.returnPressed.connect(self._commit_rename)
        layout.addWidget(self.title_editor, 1)

        self.full_title = ""
        self._hovered = False
        self._active = False
        
        # Action Buttons Layout
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(2)

        self.rename_btn = QPushButton("✎", self)
        self.rename_btn.setObjectName("ChatItemRename")
        self.rename_btn.setFixedSize(22, 22)
        self.rename_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rename_btn.clicked.connect(self._start_rename)
        btn_layout.addWidget(self.rename_btn)
        
        self.delete_btn = QPushButton("✕", self)
        self.delete_btn.setObjectName("ChatItemDelete")
        self.delete_btn.setFixedSize(22, 22)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.conversation_id))
        btn_layout.addWidget(self.delete_btn)

        self.rename_btn.setVisible(False)
        self.delete_btn.setVisible(False)
        
        layout.addLayout(btn_layout)
        
        self.set_title(title)

    def set_title(self, title: str) -> None:
        self.full_title = title
        self._refresh_title_elide()

    def set_active(self, active: bool) -> None:
        was_active = self._active
        self._active = active
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)
        self._update_action_buttons_visibility()
        if active and not was_active:
            animate_opacity_pulse(self, duration=220)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.conversation_id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent | None) -> None:
        self._start_rename()
        if event:
            event.accept()

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self._hovered = True
        self._update_action_buttons_visibility()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._hovered = False
        self._update_action_buttons_visibility()
        super().leaveEvent(event)

    def _start_rename(self) -> None:
        self.title_editor.setText(self.full_title)
        self.title_label.setVisible(False)
        self.title_editor.setVisible(True)
        self.title_editor.selectAll()
        self.title_editor.setFocus()

    def _commit_rename(self) -> None:
        new_title = self.title_editor.text().strip()
        if not new_title:
            new_title = self.full_title
        self.set_title(new_title)
        self.title_editor.setVisible(False)
        self.title_label.setVisible(True)
        self.rename_requested.emit(self.conversation_id, new_title)
        self._update_action_buttons_visibility()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._refresh_title_elide()

    def _refresh_title_elide(self) -> None:
        # Reserve right-side space for action buttons and margins.
        available = max(self.width() - 108, 72)
        fm = self.fontMetrics()
        elided = fm.elidedText(self.full_title, Qt.TextElideMode.ElideRight, available)
        self.title_label.setText(elided)
        self.title_label.setToolTip(self.full_title)

    def _update_action_buttons_visibility(self) -> None:
        editing = self.title_editor.isVisible()
        show = self._hovered or self._active or editing
        self.rename_btn.setVisible(show)
        self.delete_btn.setVisible(show and not editing)


# ---------------------------------------------------------------------------
# Sidebar widget
# ---------------------------------------------------------------------------

class Sidebar(QWidget):
    """Collapsible chat history sidebar."""

    new_chat_requested = pyqtSignal()
    chat_selected = pyqtSignal(str)
    chat_renamed = pyqtSignal(str, str)
    chat_deleted = pyqtSignal(str)
    theme_toggled = pyqtSignal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setMinimumWidth(0)
        self.setMaximumWidth(SIDEBAR_MAX_WIDTH)
        self.resize(SIDEBAR_EXPANDED_WIDTH, self.height())
        self._expanded = True
        self._expanded_width = SIDEBAR_EXPANDED_WIDTH

        self._active_id: str | None = None
        self._items: dict[str, ChatItem] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Content wrapper (everything hidden when collapsed)
        self._content = QWidget(self)
        self._content.setObjectName("SidebarContent")
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # --- Top: New Chat button ---
        top_frame = QFrame(self._content)
        top_frame.setObjectName("SidebarTop")
        top_layout = QVBoxLayout(top_frame)
        top_layout.setContentsMargins(12, 14, 12, 10)

        self.new_chat_btn = QPushButton("＋  New Chat", top_frame)
        self.new_chat_btn.setObjectName("NewChatBtn")
        self.new_chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_chat_btn.setMinimumHeight(40)
        self.new_chat_btn.clicked.connect(self.new_chat_requested.emit)
        top_layout.addWidget(self.new_chat_btn)

        content_layout.addWidget(top_frame)

        # --- Middle: scrollable chat list ---
        self.scroll = QScrollArea(self._content)
        self.scroll.setObjectName("SidebarScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.list_widget = QWidget(self.scroll)
        self.list_widget.setObjectName("SidebarList")
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(6, 6, 6, 6)
        self.list_layout.setSpacing(2)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll.setWidget(self.list_widget)
        content_layout.addWidget(self.scroll, 1)

        # --- Bottom: theme switch + brand ---
        bottom_frame = QFrame(self._content)
        bottom_frame.setObjectName("SidebarBottom")
        bottom_layout = QHBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(12, 10, 12, 12)
        bottom_layout.setSpacing(8)

        cortx_label = QLabel("CortX", bottom_frame)
        cortx_label.setObjectName("SidebarBrand")
        bottom_layout.addWidget(cortx_label)

        bottom_layout.addStretch(1)

        theme_label = QLabel("Theme", bottom_frame)
        theme_label.setObjectName("SidebarThemeLabel")
        bottom_layout.addWidget(theme_label)

        self.theme_switch = ThemeSwitch(bottom_frame)
        self.theme_switch.setObjectName("ThemeSwitch")
        self.theme_switch.toggled.connect(lambda checked: self.theme_toggled.emit(checked))
        bottom_layout.addWidget(self.theme_switch)

        content_layout.addWidget(bottom_frame)
        layout.addWidget(self._content)

    # ------------------------------------------------------------------
    # Collapse / expand
    # ------------------------------------------------------------------

    @property
    def is_expanded(self) -> bool:
        return self._expanded

    def toggle(self) -> None:
        if self._expanded:
            self.collapse()
        else:
            self.expand()

    def collapse(self) -> None:
        if self.width() > SIDEBAR_COLLAPSED_WIDTH:
            self._expanded_width = max(SIDEBAR_MIN_RESTORE_WIDTH, min(self.width(), SIDEBAR_MAX_WIDTH))
        self._expanded = False
        self._content.setVisible(False)
        self.setMaximumWidth(SIDEBAR_COLLAPSED_WIDTH)

    def expand(self) -> None:
        self._expanded = True
        self._content.setVisible(True)
        self.setMaximumWidth(SIDEBAR_MAX_WIDTH)

    @property
    def expanded_width(self) -> int:
        return self._expanded_width

    def set_expanded_width(self, width: int) -> None:
        self._expanded_width = max(SIDEBAR_MIN_RESTORE_WIDTH, min(int(width), SIDEBAR_MAX_WIDTH))

    def update_from_splitter_width(self, width: int) -> None:
        width = int(width)
        if width <= SIDEBAR_COLLAPSED_WIDTH + 2:
            self._expanded = False
            self._content.setVisible(False)
            self.setMaximumWidth(SIDEBAR_COLLAPSED_WIDTH)
            return

        self._expanded = True
        self._content.setVisible(True)
        self.setMaximumWidth(SIDEBAR_MAX_WIDTH)
        self.set_expanded_width(width)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_conversations(self, conversations: list[dict[str, Any]]) -> None:
        self._clear_items()
        for conv in conversations:
            self._add_item(conv["id"], conv["title"])

    def add_conversation(self, conversation_id: str, title: str) -> None:
        self._add_item(conversation_id, title, prepend=True)

    def set_active(self, conversation_id: str | None) -> None:
        self._active_id = conversation_id
        for cid, item in self._items.items():
            item.set_active(cid == conversation_id)

    def update_title(self, conversation_id: str, title: str) -> None:
        item = self._items.get(conversation_id)
        if item:
            item.set_title(title)

    def get_title(self, conversation_id: str) -> str | None:
        item = self._items.get(conversation_id)
        return item.full_title if item else None

    def remove_conversation(self, conversation_id: str) -> None:
        item = self._items.pop(conversation_id, None)
        if item:
            item.setParent(None)
            item.deleteLater()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _clear_items(self) -> None:
        for item in self._items.values():
            item.setParent(None)
            item.deleteLater()
        self._items.clear()

    def _add_item(self, conversation_id: str, title: str, prepend: bool = False) -> None:
        item = ChatItem(conversation_id, title, self.list_widget)
        item.clicked.connect(self._on_item_clicked)
        item.rename_requested.connect(self.chat_renamed.emit)
        item.delete_requested.connect(self.chat_deleted.emit)
        self._items[conversation_id] = item
        if prepend:
            self.list_layout.insertWidget(0, item)
            animate_widget_entrance(item, duration=190)
        else:
            self.list_layout.addWidget(item)

    def _on_item_clicked(self, conversation_id: str) -> None:
        self.set_active(conversation_id)
        self.chat_selected.emit(conversation_id)
