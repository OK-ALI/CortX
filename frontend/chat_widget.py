"""Chat area with markdown-rendered messages, sources, and status indicators."""
from __future__ import annotations

from typing import Literal

from PyQt6.QtCore import QEasingCurve, QPoint, Qt, QUrl, QTimer, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QContextMenuEvent, QDesktopServices, QPainter, QPen, QColor, QMouseEvent, QFontMetrics
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

import markdown
from frontend.ui_motion import (
    adaptive_reveal_duration,
    animate_opacity_pulse,
    animate_scrollbar_to,
    animate_widget_entrance,
    animate_widget_exit,
    profile_duration,
)

MessageRole = Literal["user", "assistant", "status"]


class SpinnerWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self._angle = 0
        self._color = QColor("#0ea5e9") # default cyan
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self._timer.start(30)

        self._color_anim = QTimer(self)
        self._color_anim.timeout.connect(self._pulse_color)
        self._color_anim.start(820)
        self._pulse_state = False

    def _rotate(self) -> None:
        self._angle = (self._angle + 12) % 360
        self.update()

    def _pulse_color(self) -> None:
        self._pulse_state = not self._pulse_state
        self._set_color(QColor("#38bdf8") if self._pulse_state else QColor("#0ea5e9"))

    def _get_color(self) -> QColor:
        return self._color

    def _set_color(self, c: QColor) -> None:
        self._color = c
        self.update()

    spinnerColor = pyqtProperty(QColor, _get_color, _set_color)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        pen = QPen(self._color)
        pen.setWidth(3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        rect = self.rect().adjusted(3, 3, -3, -3)
        painter.drawArc(rect, -self._angle * 16, 280 * 16)


class InteractiveTextBrowser(QTextBrowser):
    selection_released = pyqtSignal()
    context_menu_requested = pyqtSignal(QPoint)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # type: ignore[override]
        self.context_menu_requested.emit(event.pos())
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.selection_released.emit()


def _md_to_html(text: str) -> str:
    """Convert markdown text to HTML for rendering in QTextBrowser."""
    html = markdown.markdown(
        text,
        extensions=["fenced_code", "tables", "nl2br"],
    )
    return html


class MessageCard(QFrame):
    action_requested = pyqtSignal(str, str, str)
    selected_text_action_requested = pyqtSignal(str, str)

    def __init__(
        self,
        text: str,
        role: MessageRole,
        sources: list[str] | None = None,
        context_hint: dict | None = None,
        context_id: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.role = role
        self.context_id = context_id or ""
        self.setObjectName(f"MessageCard_{role}")
        self._is_previous = False
        self._raw_text = text
        self._context_hint = context_hint or {}
        self._last_selection_popup_text = ""
        self.setProperty("isPrevious", False)
        self.setProperty("hovered", False)
        self.setProperty("contextTarget", False)

        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(6)

        if role == "assistant":
            self.body = InteractiveTextBrowser(self)
            self.body.setObjectName("AssistantBody")
            self.body.setOpenExternalLinks(True)
            self.body.setReadOnly(True)
            self.body.setFrameShape(QFrame.Shape.NoFrame)
            
            html_content = _md_to_html(text)
            
            if sources:
                html_content += "<hr style='margin: 14px 0; border: none; border-top: 1px solid #3f475a;'/>"
                html_content += "<div style='font-weight: bold; margin-bottom: 6px; color: #94a3b8;'>Sources</div>"
                html_content += "<ul style='margin-top: 0; padding-left: 20px;'>"
                
                seen_urls = set()
                for src in sources:
                    import re
                    match = re.search(r"https?://[^\s\]\)]+", src)
                    url = match.group(0) if match else src
                    
                    clean_url = url.rstrip('/')
                    if clean_url in seen_urls:
                        continue
                    seen_urls.add(clean_url)
                    
                    idx_match = re.search(r"\[\d+\]", src)
                    idx_str = idx_match.group(0) if idx_match else ""
                    
                    display = url if len(url) < 65 else url[:62] + "..."
                    html_content += f"<li style='margin-bottom: 4px;'>{idx_str} <a href='{url}' style='color: #0ea5e9; text-decoration: none;'>{display}</a></li>"
                html_content += "</ul>"

            self.body.setHtml(html_content)
            self.body.document().setDocumentMargin(4)
            self.body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            self.body.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.body.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            card_layout.addWidget(self.body)
            # Reliable height fitting via signal instead of timers
            self.body.document().documentLayout().documentSizeChanged.connect(self._fit_body_height)
            self._fit_body_height()
            self._wire_body_interactions()

        elif role == "status":
            self.spinner = SpinnerWidget(self)
            self.spinner.setObjectName("StatusSpinner")

            self.body = QLabel(text, self)
            self.body.setObjectName("StatusBody")
            self.body.setWordWrap(False)
            self.body.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            status_layout = QHBoxLayout()
            status_layout.setContentsMargins(0, 0, 0, 0)
            status_layout.setSpacing(12)
            status_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            status_layout.addWidget(self.spinner)
            status_layout.addWidget(self.body)

            card_layout.addLayout(status_layout)

        else:
            # User message - QTextBrowser for reliable word wrap
            hint_text = self._build_user_context_hint_text()
            if hint_text:
                self.hint = QLabel(hint_text, self)
                self.hint.setObjectName("UserContextHint")
                self.hint.setWordWrap(False)
                card_layout.addWidget(self.hint)

            self.body = InteractiveTextBrowser(self)
            self.body.setObjectName("UserBody")
            self.body.setReadOnly(True)
            self.body.setFrameShape(QFrame.Shape.NoFrame)
            self.body.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.body.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.body.setPlainText(text)
            self.body.document().setDocumentMargin(0)
            self.body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            card_layout.addWidget(self.body)
            self.body.document().documentLayout().documentSizeChanged.connect(self._fit_body_height)
            self._fit_body_height()
            self._fit_user_width()
            self._wire_body_interactions()

    def _wire_body_interactions(self) -> None:
        if not isinstance(self.body, InteractiveTextBrowser):
            return
        self.body.context_menu_requested.connect(self._show_body_context_menu)
        self.body.selection_released.connect(self._show_selection_popup_if_any)

    def set_previous(self, value: bool) -> None:
        self._is_previous = value
        self.setProperty("isPrevious", value)
        if not value:
            self.setProperty("hovered", False)
        self._refresh_style()

    def set_context_target(self, value: bool) -> None:
        self.setProperty("contextTarget", bool(value))
        self._refresh_style()

    def enterEvent(self, event) -> None:  # type: ignore[override]
        if self._is_previous and self.role in {"user", "assistant"}:
            self.setProperty("hovered", True)
            self._refresh_style()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        if self.property("hovered"):
            self.setProperty("hovered", False)
            self._refresh_style()
        super().leaveEvent(event)

    def _refresh_style(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # type: ignore[override]
        if self.role == "status":
            super().contextMenuEvent(event)
            return
        self._show_card_context_menu(event.globalPos())
        event.accept()

    def _show_card_context_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        reply_action = menu.addAction("Reply to this")
        follow_action = menu.addAction("Follow this topic")
        update_action = menu.addAction("Check for new updates")
        chosen = menu.exec(global_pos)
        context_seed = self._build_context_seed()
        if chosen == reply_action:
            self.action_requested.emit("reply", context_seed, self.context_id)
        elif chosen == follow_action:
            self.action_requested.emit("follow", context_seed, self.context_id)
        elif chosen == update_action:
            self.action_requested.emit("update", context_seed, self.context_id)

    def _selected_text(self) -> str:
        if not hasattr(self, "body") or not isinstance(self.body, QTextBrowser):
            return ""
        return " ".join(self.body.textCursor().selectedText().split()).strip()

    def _show_body_context_menu(self, pos: QPoint) -> None:
        if not isinstance(self.body, QTextBrowser):
            return

        menu = QMenu(self)
        reply_action = menu.addAction("Reply to this")
        follow_action = menu.addAction("Follow this topic")
        update_action = menu.addAction("Check for new updates")

        selected_text = self._selected_text()
        ask_selected = explain_selected = updates_selected = None
        if selected_text:
            menu.addSeparator()
            ask_selected = menu.addAction("Ask about selected text")
            explain_selected = menu.addAction("Explain selected text")
            updates_selected = menu.addAction("Latest updates on selected text")

        menu.addSeparator()
        standard = self.body.createStandardContextMenu()
        for action in standard.actions():
            menu.addAction(action)
        standard.deleteLater()

        chosen = menu.exec(self.body.mapToGlobal(pos))
        context_seed = self._build_context_seed()
        if chosen == reply_action:
            self.action_requested.emit("reply", context_seed, self.context_id)
        elif chosen == follow_action:
            self.action_requested.emit("follow", context_seed, self.context_id)
        elif chosen == update_action:
            self.action_requested.emit("update", context_seed, self.context_id)
        elif chosen == ask_selected and selected_text:
            self.selected_text_action_requested.emit("ask", selected_text)
        elif chosen == explain_selected and selected_text:
            self.selected_text_action_requested.emit("explain", selected_text)
        elif chosen == updates_selected and selected_text:
            self.selected_text_action_requested.emit("update", selected_text)

    def _show_selection_popup_if_any(self) -> None:
        selected_text = self._selected_text()
        if not selected_text:
            self._last_selection_popup_text = ""
            return

        if selected_text == self._last_selection_popup_text:
            return
        self._last_selection_popup_text = selected_text

        menu = QMenu(self)
        ask_action = menu.addAction("Ask")
        explain_action = menu.addAction("Explain")
        update_action = menu.addAction("Latest updates")

        if isinstance(self.body, QTextBrowser):
            anchor = self.body.cursorRect().bottomRight()
            global_pos = self.body.mapToGlobal(anchor)
        else:
            global_pos = self.mapToGlobal(self.rect().center())

        chosen = menu.exec(global_pos)
        if chosen == ask_action:
            self.selected_text_action_requested.emit("ask", selected_text)
        elif chosen == explain_action:
            self.selected_text_action_requested.emit("explain", selected_text)
        elif chosen == update_action:
            self.selected_text_action_requested.emit("update", selected_text)

    def _build_context_seed(self) -> str:
        compact = " ".join(self._raw_text.split()).strip()
        if len(compact) <= 320:
            return compact
        return f"{compact[:317]}..."

    def _fit_body_height(self, *args, **kwargs) -> None:
        """Resize QTextBrowser to fit its content exactly."""
        if not hasattr(self, 'body') or not isinstance(self.body, QTextBrowser):
            return
        doc_height = int(self.body.document().size().height())
        target = max(doc_height + 8, 24)
        if self.body.height() != target:
            self.body.setMinimumHeight(target)
            self.body.setMaximumHeight(target)

    def _fit_user_width(self) -> None:
        """Let user bubbles size to their text content with a sane max width."""
        if self.role != "user":
            return
        text = " ".join(self._raw_text.split())
        hint_text = self._build_user_context_hint_text()
        if not text:
            self.setMinimumWidth(90)
            self.setMaximumWidth(320)
            return

        metrics = QFontMetrics(self.body.font())
        line_width = metrics.horizontalAdvance(text[:1000])
        if hint_text:
            line_width = max(line_width, metrics.horizontalAdvance(hint_text[:220]))
        # Keep user bubbles compact while allowing room for medium-length prompts.
        target_width = max(120, min(line_width + 54, 560))
        self.setMinimumWidth(90)
        self.setMaximumWidth(target_width)

    def _build_user_context_hint_text(self) -> str:
        if self.role != "user" or not self._context_hint:
            return ""
        label = " ".join(str(self._context_hint.get("label", "")).split()).strip()
        preview = " ".join(str(self._context_hint.get("preview", "")).split()).strip()
        if not label and not preview:
            return ""
        if len(preview) > 95:
            preview = f"{preview[:92]}..."
        return f"{label}: {preview}" if preview else label

    def resizeEvent(self, event) -> None:
        """Re-fit height when the card is resized (window resize, etc)."""
        super().resizeEvent(event)
        self._fit_body_height()

    @staticmethod
    def _extract_url(source_text: str) -> str:
        import re
        match = re.search(r"https?://[^\s\]\)]+", source_text)
        return match.group(0) if match else source_text

    @staticmethod
    def _open_link(url: QUrl) -> None:
        QDesktopServices.openUrl(url)


class ChatWidget(QWidget):
    context_action_requested = pyqtSignal(str, str, str)
    selected_text_action_requested = pyqtSignal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ChatWidget")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("ChatScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.viewport_widget = QWidget(self.scroll)
        self.viewport_widget.setObjectName("ChatViewport")
        self.messages_layout = QVBoxLayout(self.viewport_widget)
        self.messages_layout.setContentsMargins(40, 24, 40, 24)
        self.messages_layout.setSpacing(16)
        self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.welcome = QLabel("What would you like to research?", self.viewport_widget)
        self.welcome.setObjectName("WelcomeMessage")
        self.welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.welcome.setWordWrap(True)
        self.messages_layout.addWidget(self.welcome)

        self.scroll.setWidget(self.viewport_widget)
        root_layout.addWidget(self.scroll)

        self._status_card: MessageCard | None = None
        self._message_cards: list[MessageCard] = []
        self._message_counter = 0
        self._cards_by_context_id: dict[str, MessageCard] = {}
        self._wrappers_by_context_id: dict[str, QWidget] = {}
        self._active_context_target_id: str | None = None
        self._motion_profile = "balanced"

    def set_motion_profile(self, profile: str) -> None:
        self._motion_profile = profile if profile in {"snappy", "balanced", "cinematic"} else "balanced"

    def clear_chat(self) -> None:
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._status_card = None
        self._message_cards.clear()
        self._message_counter = 0
        self._cards_by_context_id.clear()
        self._wrappers_by_context_id.clear()
        self._active_context_target_id = None
        self.welcome = QLabel("What would you like to research?", self.viewport_widget)
        self.welcome.setObjectName("WelcomeMessage")
        self.welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.welcome.setWordWrap(True)
        self.messages_layout.addWidget(self.welcome)

    def add_user_message(self, text: str, context_id: str | None = None, context_hint: dict | None = None) -> None:
        self._hide_welcome()
        self._add_message(
            text=text,
            role="user",
            align=Qt.AlignmentFlag.AlignRight,
            context_hint=context_hint,
            context_id=context_id,
            animate=True,
        )

    def add_assistant_message(self, text: str, sources: list[str] | None = None, context_id: str | None = None) -> None:
        self._remove_status()
        self._add_message(
            text=text,
            role="assistant",
            align=Qt.AlignmentFlag.AlignLeft,
            sources=sources,
            context_id=context_id,
            animate=True,
        )

    def set_status(self, text: str) -> None:
        self._hide_welcome()
        if self._status_card is not None:
            if hasattr(self._status_card.body, 'setText'):
                self._status_card.body.setText(text)
            return
        self._add_message(text=text, role="status", align=Qt.AlignmentFlag.AlignHCenter, animate=True)

    def load_messages(self, messages: list[dict]) -> None:
        self._clear_all()
        if not messages:
            return
        self._hide_welcome()
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            sources = msg.get("sources", [])
            context_id = str(msg.get("id", "")).strip() or None
            if role == "user":
                self._add_message(
                    text=content,
                    role="user",
                    align=Qt.AlignmentFlag.AlignRight,
                    context_hint=None,
                    context_id=context_id,
                    animate=False,
                )
            elif role == "assistant":
                self._add_message(
                    text=content, role="assistant",
                    align=Qt.AlignmentFlag.AlignLeft,
                    sources=sources if sources else None,
                    context_id=context_id,
                    animate=False,
                )

    def _hide_welcome(self) -> None:
        if self.welcome:
            self.welcome.hide()

    def _clear_all(self) -> None:
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._status_card = None
        self._message_cards.clear()
        self._message_counter = 0
        self._cards_by_context_id.clear()
        self._wrappers_by_context_id.clear()
        self._active_context_target_id = None
        self.welcome = QLabel("What would you like to research?", self.viewport_widget)
        self.welcome.setObjectName("WelcomeMessage")
        self.welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.welcome.setWordWrap(True)
        self.messages_layout.addWidget(self.welcome)

    def _remove_status(self) -> None:
        if self._status_card is not None:
            parent_wrapper = self._status_card.parent()
            if parent_wrapper:
                def _cleanup() -> None:
                    parent_wrapper.setParent(None)
                    parent_wrapper.deleteLater()

                animate_widget_exit(
                    parent_wrapper,
                    duration=profile_duration(self._motion_profile, snappy=120, balanced=160, cinematic=220),
                    on_finished=_cleanup,
                )
            if self._status_card in self._message_cards:
                self._message_cards.remove(self._status_card)
            self._status_card = None

    def _add_message(
        self,
        text: str,
        role: MessageRole,
        align: Qt.AlignmentFlag,
        sources: list[str] | None = None,
        context_hint: dict | None = None,
        context_id: str | None = None,
        animate: bool = False,
    ) -> None:
        for existing_card in self._message_cards:
            existing_card.set_previous(True)

        message_context_id = context_id or self._next_context_id()

        wrapper = QWidget(self.viewport_widget)
        wrapper.setObjectName("MessageWrapper")
        row = QHBoxLayout(wrapper)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        card = MessageCard(
            text=text,
            role=role,
            sources=sources,
            context_hint=context_hint,
            context_id=message_context_id,
            parent=wrapper,
        )

        if role == "assistant":
            card.setMinimumWidth(300)
            card.setMaximumWidth(900)
            card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        elif role == "user":
            card.setMinimumWidth(80)
            card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        else:
            # Status — no max constraint, let it be as wide as needed
            card.setMinimumWidth(200)
            card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        row.addWidget(card, 0, align)
        self.messages_layout.addWidget(wrapper)
        self._message_cards.append(card)

        if role != "status":
            self._cards_by_context_id[message_context_id] = card
            self._wrappers_by_context_id[message_context_id] = wrapper

        card.action_requested.connect(self.context_action_requested.emit)
        card.selected_text_action_requested.connect(self.selected_text_action_requested.emit)

        card.set_previous(False)

        if role == "status":
            self._status_card = card

        if animate and role in {"assistant", "user", "status"}:
            if role == "assistant":
                duration = adaptive_reveal_duration(
                    len(text),
                    has_sources=bool(sources),
                    profile=self._motion_profile,
                )
            elif role == "user":
                duration = profile_duration(self._motion_profile, snappy=140, balanced=190, cinematic=260)
            else:
                duration = profile_duration(self._motion_profile, snappy=120, balanced=160, cinematic=220)
            animate_widget_entrance(
                wrapper,
                duration=duration,
                follow_scrollbar=self.scroll.verticalScrollBar(),
            )

        if not (animate and role in {"assistant", "user", "status"}):
            QTimer.singleShot(50, lambda: self._scroll_to_bottom(animated=False))

    def _scroll_to_bottom(self, animated: bool = False) -> None:
        bar = self.scroll.verticalScrollBar()
        target = bar.maximum()
        if animated:
            animate_scrollbar_to(bar, target, duration=220)
        else:
            bar.setValue(target)

    def focus_message(self, context_id: str) -> None:
        card = self._cards_by_context_id.get(context_id)
        wrapper = self._wrappers_by_context_id.get(context_id)
        if card is None or wrapper is None:
            return

        if self._active_context_target_id:
            previous = self._cards_by_context_id.get(self._active_context_target_id)
            if previous is not None:
                previous.set_context_target(False)

        self._active_context_target_id = context_id
        card.set_context_target(True)
        animate_opacity_pulse(
            card,
            duration=profile_duration(self._motion_profile, snappy=170, balanced=220, cinematic=280),
        )

        bar = self.scroll.verticalScrollBar()
        target = max(wrapper.y() - 24, 0)
        animate_scrollbar_to(
            bar,
            target,
            duration=profile_duration(self._motion_profile, snappy=180, balanced=240, cinematic=320),
        )

        def _clear_target() -> None:
            if self._active_context_target_id != context_id:
                return
            focused = self._cards_by_context_id.get(context_id)
            if focused is not None:
                focused.set_context_target(False)
            self._active_context_target_id = None

        QTimer.singleShot(1800, _clear_target)

    def _next_context_id(self) -> str:
        self._message_counter += 1
        return f"msg-{self._message_counter}"
