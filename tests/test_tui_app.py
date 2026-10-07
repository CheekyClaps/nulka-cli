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
            assert not sidebar.has_class("hidden")
            
            # Toggle off
            app.action_toggle_sidebar()
            assert sidebar.has_class("hidden")
            
            # Toggle on
            app.action_toggle_sidebar()
            assert not sidebar.has_class("hidden")
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
