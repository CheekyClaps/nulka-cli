"""Textual TUI Application for NulkaCLI.
Provides an asynchronous, multi-pane terminal interface with:
- Workspace DirectoryTree sidebar
- Main Chat Feed (Markdown / Rich-rendered messages)
- Collapsible Action Drawer for live tool streaming
- Non-blocking async agent worker integration
"""

import os
from pathlib import Path
from typing import Callable, Optional

from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll, Center
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    DirectoryTree,
    Footer,
    Header,
    Input,
    Label,
    LoadingIndicator,
    RichLog,
    Static,
)

class HelpScreen(ModalScreen):
    """Screen with a dialog for help and keybindings."""
    
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Close Help"),
    ]
    
    CSS = """
    HelpScreen {
        align: center middle;
        background: $background 50%;
    }
    
    #help-dialog {
        width: 80%;
        height: 80%;
        padding: 1 2;
        border: thick $primary;
        background: #1e1f29;
    }
    
    #help-dialog-title {
        text-align: center;
        text-style: bold;
        color: #8be9fd;
        margin-bottom: 1;
        border-bottom: solid #2a2c37;
    }
    """
    
    def compose(self) -> ComposeResult:
        help_text = """
# NulkaCLI Help

## Keybindings
- **Ctrl+B**: Toggle Workspace Sidebar
- **Ctrl+D**: Toggle Action Drawer
- **Ctrl+Y**: Copy Last Assistant Response to Clipboard
- **Ctrl+C**: Cancel Action / Copy selected input text
- **F1**: Show this Help Screen
- **Esc**: Close this Help Screen

## Copying & Pasting in the TUI
- **Copy with Mouse**: Hold **Shift** while dragging your mouse, then press `Ctrl+Shift+C` (or right-click -> Copy). This bypasses the TUI's mouse capture.
- **Copy Last Output**: Press **Ctrl+Y** or type `/copy` to instantly copy the last AI response to your system clipboard.
- **Click to Copy**: Click on any message card in the chat to copy its text directly to your clipboard.
- **Paste into Prompt**: Press `Ctrl+V` or `Ctrl+Shift+V` to paste text into the input field.

## Slash Commands
- `/help` or `/?`: Show help info
- `/tools`: List available capabilities
- `/agents`: List specialized AI departments
- `/clear`: Clear chat screen
- `/tui` / `/repl`: Switch modes
- `/quit`: Exit application
- `/copy`: Copy last output to clipboard
- `/expand`: View last truncated output in pager
- `/models`, `/pull`, `/load`: Ollama Model Management
- `/hrf`, `/trust`, `/doubt`: Manage Hallucination Risk Factor

*(Press ESC to close)*
        """
        with Vertical(id="help-dialog"):
            yield Label("NulkaCLI Help & Commands", id="help-dialog-title")
            yield Static(Markdown(help_text))


from typing import Any

class InfoScreen(ModalScreen):
    """Generic screen with a dialog for displaying markdown or rich renderable info."""
    
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Close"),
    ]
    
    CSS = """
    InfoScreen {
        align: center middle;
        background: $background 50%;
    }
    
    #info-dialog {
        width: 80%;
        height: 80%;
        padding: 1 2;
        border: thick $primary;
        background: #1e1f29;
    }
    
    #info-dialog-title {
        text-align: center;
        text-style: bold;
        color: #8be9fd;
        margin-bottom: 1;
        border-bottom: solid #2a2c37;
    }
    """
    
    def __init__(self, title: str, content: Any, **kwargs):
        super().__init__(**kwargs)
        self.title_text = title
        self.content = content
        
    def compose(self) -> ComposeResult:
        with Vertical(id="info-dialog"):
            yield Label(self.title_text, id="info-dialog-title")
            with VerticalScroll():
                if isinstance(self.content, str):
                    yield Static(Markdown(self.content))
                else:
                    yield Static(self.content)


class ChatMessageWidget(Static):
    """Widget displaying a single message card in the chat log."""

    def __init__(self, sender: str, content: str, role: str = "user", **kwargs):
        super().__init__(**kwargs)
        self.sender = sender
        self.content = content
        self.role = role

    def on_click(self, event) -> None:
        """Clicking on any message card copies its content to clipboard."""
        from nulka_cli.utils import copy_text_to_clipboard
        if self.content:
            if copy_text_to_clipboard(self.content):
                self.app.notify("Copied message to clipboard!", title="Clipboard")
            else:
                self.app.notify("Failed to copy message", severity="warning")

    def compose(self) -> ComposeResult:
        if self.role == "user":
            header_text = f"✦ [bold cyan]{self.sender}[/bold cyan] [dim]📋[/dim]"
            border_style = "cyan"
        elif self.role == "agent":
            header_text = f"🤖 [bold green]{self.sender}[/bold green] [dim]📋[/dim]"
            border_style = "green"
        elif self.role == "tool":
            header_text = f"⚙️ [bold yellow]{self.sender}[/bold yellow] [dim]📋[/dim]"
            border_style = "yellow"
        else:
            header_text = f"ℹ️ [bold magenta]{self.sender}[/bold magenta] [dim]📋[/dim]"
            border_style = "magenta"

        # Try to render markdown if multiline or formatted
        yield Static(header_text, classes="message-header")
        yield Static(self.content, classes="message-body")


class NulkaApp(App):
    """The main NulkaCLI Textual Application."""

    TITLE = "Nulka-CLI"

    CSS = """
    Screen {
        background: #121317;
        color: #e0e0e0;
    }

    #app-grid {
        height: 1fr;
        layout: horizontal;
    }

    #sidebar {
        width: 32;
        dock: left;
        background: #181920;
        border-right: solid #2a2c37;
        padding: 0 1;
        display: block;
    }

    #sidebar.hidden {
        display: none;
    }

    #sidebar-title {
        text-style: bold;
        color: #8be9fd;
        padding: 1 0;
        text-align: center;
        border-bottom: solid #2a2c37;
    }

    #directory-tree {
        height: 1fr;
        background: transparent;
        border: none;
    }

    #main-content {
        width: 1fr;
        height: 100%;
        layout: vertical;
    }

    #chat-scroll {
        height: 1fr;
        padding: 1;
        overflow-y: scroll;
    }

    ChatMessageWidget {
        margin: 1 0;
        padding: 1;
        background: #1e1f29;
        border-left: thick #6272a4;
    }

    ChatMessageWidget.user {
        border-left: thick #8be9fd;
        background: #1a222d;
    }

    ChatMessageWidget.agent {
        border-left: thick #50fa7b;
        background: #16241a;
    }

    ChatMessageWidget.tool-summary {
        border-left: thick #ffb86c;
        background: #25221b;
    }

    .message-header {
        margin-bottom: 1;
        text-style: bold;
    }

    .message-body {
        color: #f8f8f2;
    }

    #action-drawer {
        height: 16;
        dock: bottom;
        background: #0f1015;
        border-top: double #bd93f9;
        padding: 0 1;
        display: none;
    }

    #action-drawer.visible {
        display: block;
    }

    #action-title {
        color: #bd93f9;
        text-style: bold;
        padding: 0;
    }

    #action-log {
        height: 1fr;
        background: #0b0c0e;
        border: solid #282a36;
    }

    #input-container {
        height: 3;
        dock: bottom;
        background: #181920;
        border-top: solid #2a2c37;
        padding: 0 1;
    }

    #user-input {
        background: #121317;
        border: none;
        color: #50fa7b;
    }

    #user-input:focus {
        border: none;
    }
    """

    BINDINGS = [
        Binding("ctrl+b", "toggle_sidebar", "Toggle Sidebar", priority=True),
        Binding("ctrl+d", "toggle_action_drawer", "Toggle Action Drawer", priority=True),
        Binding("ctrl+y", "copy_last_output", "Copy Output", priority=True),
        Binding("ctrl+c", "cancel_action", "Cancel / Copy", priority=False),
        Binding("f1", "show_help", "Help", priority=True),
    ]

    is_thinking = reactive(False)
    sidebar_visible = reactive(True)
    action_drawer_visible = reactive(False)

    def __init__(
        self,
        workspace_dir: Optional[str] = None,
        on_submit_callback: Optional[Callable[[str, "NulkaApp"], None]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.workspace_dir = workspace_dir or os.getcwd()
        self.on_submit_callback = on_submit_callback

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Container(id="app-grid"):
            # Left Sidebar: Workspace explorer
            with Vertical(id="sidebar"):
                yield Label("📂 Workspace", id="sidebar-title")
                yield DirectoryTree(self.workspace_dir, id="directory-tree")

            # Center: Main Chat & Drawer
            with Vertical(id="main-content"):
                with VerticalScroll(id="chat-scroll"):
                    yield ChatMessageWidget(
                        sender="System",
                        content="Welcome to NulkaCLI TUI! Type your prompt below or use slash commands (e.g. `/help`, `/tools`).",
                        role="system",
                    )

                # Bottom Action Drawer (hidden by default)
                with Vertical(id="action-drawer"):
                    yield Label("⚡ Live Tool Stream (Action Drawer)", id="action-title")
                    yield RichLog(id="action-log", highlight=True, markup=True)

                # Bottom input field
                with Container(id="input-container"):
                    yield Input(placeholder="Type a message or slash command...", id="user-input")

        yield Footer()

    def on_mount(self) -> None:
        """Focus the input field on startup."""
        self.query_one("#user-input", Input).focus()
        self.current_vram_str = ""
        self.update_subtitle()
        self.set_interval(5.0, self.poll_vram_status)

    @work(thread=True)
    def poll_vram_status(self) -> None:
        from nulka_cli.utils import get_vram_status_string
        vram_str = get_vram_status_string()
        def _update():
            if self.current_vram_str != vram_str:
                self.current_vram_str = vram_str
                self.update_subtitle()
        self.app.call_from_thread(_update)

    def update_subtitle(self) -> None:
        msg = getattr(self, "_thinking_msg", "Ready") if getattr(self, "is_thinking", False) else "Ready"
        if getattr(self, "current_vram_str", ""):
            self.sub_title = f"{msg}  |  {self.current_vram_str}"
        else:
            self.sub_title = msg

    def action_toggle_sidebar(self) -> None:
        """Toggle workspace sidebar visibility."""
        self.sidebar_visible = not self.sidebar_visible
        sidebar = self.query_one("#sidebar")
        if self.sidebar_visible:
            sidebar.remove_class("hidden")
        else:
            sidebar.add_class("hidden")

    def action_toggle_action_drawer(self) -> None:
        """Toggle action drawer visibility."""
        self.action_drawer_visible = not self.action_drawer_visible
        drawer = self.query_one("#action-drawer")
        if self.action_drawer_visible:
            drawer.add_class("visible")
        else:
            drawer.remove_class("visible")

    def action_cancel_action(self) -> None:
        """Handle interrupt/cancellation or copy in input."""
        focused = self.focused
        if isinstance(focused, Input) and not focused.selection.is_empty:
            focused.action_copy()
            return
        self.add_system_message("Action cancelled by user.")
        self.set_thinking(False)

    def action_copy_last_output(self) -> None:
        """Copy the last agent response to system clipboard."""
        from nulka_cli.core.state import state
        from nulka_cli.utils import copy_text_to_clipboard

        if state.last_full_output:
            if copy_text_to_clipboard(state.last_full_output):
                self.notify("Copied last response to clipboard!", title="Clipboard")
            else:
                self.notify("Failed to copy to clipboard", severity="warning")
        else:
            self.notify("No response to copy yet", severity="information")

    def action_show_help(self) -> None:
        """Show the TUI help screen."""
        self.push_screen(HelpScreen())

    def action_show_info(self, title: str, content: Any) -> None:
        """Show a generic TUI info screen with string or rich renderable content."""
        def _apply():
            self.push_screen(InfoScreen(title, content))
        self._dispatch_ui(_apply)

    def watch_is_thinking(self, thinking: bool) -> None:
        """React to thinking state change."""
        pass # Using self.sub_title directly in set_thinking now

    def _dispatch_ui(self, fn, *args, **kwargs):
        """Helper to safely execute UI mutations on the main thread if called from worker threads."""
        import threading
        if threading.get_ident() == getattr(self, "_thread_id", None):
            return fn(*args, **kwargs)
        else:
            return self.call_from_thread(fn, *args, **kwargs)

    def set_thinking(self, thinking: bool, message: str = "⏳ Agent thinking...") -> None:
        """Update the thinking indicator."""
        def _apply():
            self.is_thinking = thinking
            self._thinking_msg = message
            self.update_subtitle()
        self._dispatch_ui(_apply)

    def add_user_message(self, content: str) -> None:
        """Append a user message to the chat view."""
        def _apply():
            chat_scroll = self.query_one("#chat-scroll", VerticalScroll)
            widget = ChatMessageWidget("You", content, role="user", classes="user")
            chat_scroll.mount(widget)
            widget.scroll_visible()
        self._dispatch_ui(_apply)

    def add_agent_message(self, sender: str, content: str) -> None:
        """Append an agent message to the chat view."""
        def _apply():
            chat_scroll = self.query_one("#chat-scroll", VerticalScroll)
            widget = ChatMessageWidget(sender, content, role="agent", classes="agent")
            chat_scroll.mount(widget)
            widget.scroll_visible()
        self._dispatch_ui(_apply)

    def add_tool_summary(self, title: str, summary: str) -> None:
        """Append a condensed tool execution chip/card to the chat view."""
        def _apply():
            chat_scroll = self.query_one("#chat-scroll", VerticalScroll)
            widget = ChatMessageWidget(title, summary, role="tool", classes="tool-summary")
            chat_scroll.mount(widget)
            widget.scroll_visible()
        self._dispatch_ui(_apply)

    def add_system_message(self, content: str) -> None:
        """Append a system notification."""
        def _apply():
            chat_scroll = self.query_one("#chat-scroll", VerticalScroll)
            widget = ChatMessageWidget("System", content, role="system")
            chat_scroll.mount(widget)
            widget.scroll_visible()
        self._dispatch_ui(_apply)

    def stream_action(self, line: str, open_drawer: bool = True) -> None:
        """Write output into the action drawer log."""
        def _apply():
            if open_drawer and not self.action_drawer_visible:
                self.action_toggle_action_drawer()
            action_log = self.query_one("#action-log", RichLog)
            action_log.write(line)
        self._dispatch_ui(_apply)

    def clear_chat(self) -> None:
        """Clears all messages from the chat scroll view and resets to clean state."""
        def _apply():
            chat_scroll = self.query_one("#chat-scroll", VerticalScroll)
            chat_scroll.remove_children()
            chat_scroll.mount(ChatMessageWidget(
                sender="System",
                content="Chat context cleared. Type your prompt below.",
                role="system"
            ))
        self._dispatch_ui(_apply)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user input submission."""
        user_text = event.value.strip()
        if not user_text:
            return

        # Clear input field immediately
        event.input.value = ""

        # Display user message
        self.add_user_message(user_text)

        # Trigger callback or background worker
        if self.on_submit_callback:
            self.run_worker_submit(user_text)

    @work(thread=True)
    def run_worker_submit(self, user_text: str) -> None:
        """Runs the submission callback in a separate worker thread so UI never freezes."""
        self.app.call_from_thread(self.set_thinking, True, "⏳ Analyzing intent...")
        try:
            if self.on_submit_callback:
                self.on_submit_callback(user_text, self)
        except Exception as e:
            self.app.call_from_thread(self.add_system_message, f"❌ Error during execution: {e}")
        finally:
            self.app.call_from_thread(self.set_thinking, False)
