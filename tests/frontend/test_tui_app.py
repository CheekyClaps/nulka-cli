import asyncio
from nulka_cli.ui.tui_app import NulkaApp, ChatMessageWidget
from textual.widgets import Input, DirectoryTree, RichLog, Label

def test_nulka_app_composition_and_mounting(tmp_path):
    """Test that NulkaApp composes all expected widgets properly."""
    async def _test():
        app = NulkaApp(workspace_dir=str(tmp_path))
        async with app.run_test() as pilot:
            assert app.query_one("#sidebar") is not None
            assert app.query_one(DirectoryTree) is not None
            assert app.query_one("#chat-scroll") is not None
            assert app.query_one("#action-drawer") is not None
            assert app.query_one("#action-log", RichLog) is not None
            assert app.query_one("#user-input", Input) is not None
    asyncio.run(_test())

def test_tui_sidebar_toggle(tmp_path):
    """Test toggling the sidebar via action."""
    async def _test():
        app = NulkaApp(workspace_dir=str(tmp_path))
        async with app.run_test() as pilot:
            sidebar = app.query_one("#sidebar")
            # Starts hidden by default
            assert sidebar.has_class("hidden")
            
            # Toggle on
            app.action_toggle_sidebar()
            assert not sidebar.has_class("hidden")
            
            # Toggle off
            app.action_toggle_sidebar()
            assert sidebar.has_class("hidden")
    asyncio.run(_test())

def test_tui_action_drawer_stream(tmp_path):
    """Test action drawer streaming and visibility toggle."""
    async def _test():
        app = NulkaApp(workspace_dir=str(tmp_path))
        async with app.run_test() as pilot:
            drawer = app.query_one("#action-drawer")
            assert not drawer.has_class("visible")
            
            # Streaming with open_drawer=True should open it
            app.stream_action("Executing shell: pytest", open_drawer=True)
            assert drawer.has_class("visible")
            
            # Toggle drawer visibility
            app.action_toggle_action_drawer()
            assert not drawer.has_class("visible")
    asyncio.run(_test())

def test_tui_chat_messages(tmp_path):
    """Test adding user, agent, tool, and system messages."""
    async def _test():
        app = NulkaApp(workspace_dir=str(tmp_path))
        async with app.run_test() as pilot:
            app.add_user_message("Hello from user")
            app.add_agent_message("Strategist", "Plan ready")
            app.add_tool_summary("Shell", "[✓ Ran npm test: passed]")
            app.add_system_message("Notification")
            
            chat_scroll = app.query_one("#chat-scroll")
            messages = chat_scroll.query(ChatMessageWidget)
            
            # 1 default welcome message + 4 added messages = 5
            assert len(messages) == 5
    asyncio.run(_test())

def test_tui_input_submission_with_callback(tmp_path):
    """Test user input submission triggering the background worker."""
    async def _test():
        submitted_prompts = []

        def mock_on_submit(prompt: str, app_instance: NulkaApp):
            submitted_prompts.append(prompt)
            app_instance.add_agent_message("Assistant", f"Echo: {prompt}")

        app = NulkaApp(workspace_dir=str(tmp_path), on_submit_callback=mock_on_submit)
        async with app.run_test() as pilot:
            input_widget = app.query_one("#user-input", Input)
            input_widget.value = "Create a new file"
            await pilot.press("enter")
            
            # Give async worker a brief moment to execute
            await pilot.pause(0.2)
            
            assert "Create a new file" in submitted_prompts
            chat_scroll = app.query_one("#chat-scroll")
            agent_msgs = [m for m in chat_scroll.query(ChatMessageWidget) if m.role == "agent"]
            assert any("Echo: Create a new file" in m.content for m in agent_msgs)
    asyncio.run(_test())

def test_tui_logs_modal_auto_tail_and_detach(tmp_path):
    """Test that LogsScreen defaults to tail, auto-scrolls with streams, and detaches when scrolled."""
    from nulka_cli.ui.tui_app import LogsScreen, LogTextArea

    async def _test():
        long_action_log = "\n".join([f"Action line {i}" for i in range(50)])
        long_thought_log = "\n".join([f"Thought line {i}" for i in range(50)])
        app = NulkaApp(workspace_dir=str(tmp_path))
        async with app.run_test() as pilot:
            # Open the logs screen modal
            app.push_screen(LogsScreen(long_action_log, long_thought_log))
            await pilot.pause()
            
            modal = app.screen
            assert isinstance(modal, LogsScreen)
            action_area = modal.query_one("#action-log-area", LogTextArea)
            
            # 1. Defaults to tail (auto_scroll active and at vertical end)
            assert action_area.auto_scroll is True
            assert action_area.is_vertical_scroll_end is True
            
            # 2. Live stream appends and follows tail
            app.stream_action("New live streamed action")
            await pilot.pause()
            assert action_area.is_vertical_scroll_end is True
            assert action_area.auto_scroll is True
            
            # 3. User scrolls up -> detaches auto_scroll
            action_area.scroll_up()
            await pilot.pause()
            assert action_area.auto_scroll is False
            assert action_area.is_vertical_scroll_end is False
            
            # 4. Appending while detached preserves user's scroll position
            saved_scroll = action_area.scroll_y
            app.stream_action("Another live streamed action while detached")
            await pilot.pause()
            assert action_area.scroll_y == saved_scroll
            assert action_area.auto_scroll is False
            
            # 5. Scrolling back to the end re-attaches
            action_area.scroll_end(animate=False)
            await pilot.pause()
            assert action_area.auto_scroll is True
            assert action_area.is_vertical_scroll_end is True
    asyncio.run(_test())

def test_chat_message_widget_rendering_no_duplicate(tmp_path):
    """Test that ChatMessageWidget renders header and body once without double text artifact."""
    from textual.containers import Container
    from textual.widgets import Static

    async def _test():
        app = NulkaApp(workspace_dir=str(tmp_path))
        async with app.run_test() as pilot:
            widget = ChatMessageWidget("ROUTER", "Please specify the directory", role="agent")
            assert isinstance(widget, Container)
            chat_scroll = app.query_one("#chat-scroll")
            chat_scroll.mount(widget)
            await pilot.pause()

            # Ensure child statics exist for header and body
            statics = widget.query(Static)
            assert len(statics) == 2
            rendered_texts = [str(s.render()) for s in statics]
            assert any("ROUTER" in t for t in rendered_texts)
            assert any("Please specify the directory" in t for t in rendered_texts)
    asyncio.run(_test())

def test_tui_system_message_copy(tmp_path):
    """Test that add_system_message updates last_full_output and action_copy_last_output copies it."""
    from unittest.mock import patch
    from nulka_cli.core.state import state

    async def _test():
        app = NulkaApp(workspace_dir=str(tmp_path))
        async with app.run_test() as pilot:
            app.add_system_message("System workspace initialized successfully.")
            await pilot.pause()

            assert state.last_full_output == "System workspace initialized successfully."

            with patch("nulka_cli.utils.copy_text_to_clipboard", return_value=True) as mock_copy:
                app.action_copy_last_output()
                assert mock_copy.called
                assert mock_copy.call_args[0][0] == "System workspace initialized successfully."
    asyncio.run(_test())


