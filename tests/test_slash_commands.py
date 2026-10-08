import os
from unittest.mock import MagicMock

import pytest

from nulka_cli.core.state import state
from nulka_cli.ui.slash_commands import handle_slash_command


@pytest.fixture
def mock_console():
    console = MagicMock()
    return console

@pytest.fixture
def mock_session():
    session = MagicMock()
    return session

@pytest.fixture
def mock_cli_module():
    return MagicMock()

def test_handle_slash_command_agents(mock_console, mock_session, mock_cli_module):
    # Ensure it doesn't trigger the TUI modal branch in testing
    del mock_session.action_show_info
    
    handled = handle_slash_command("/agents", ["/agents"], mock_console, mock_session, mock_cli_module)
    assert handled is True
    assert mock_console.print.called
    table = mock_console.print.call_args[0][0]
    
    col_names = [col.header for col in table.columns]
    assert "Agent" in col_names
    assert "Role" in col_names
    assert "Description / Goal" in col_names


def test_handle_slash_command_about(mock_console, mock_session, mock_cli_module):
    handled = handle_slash_command("/about", ["/about"], mock_console, mock_session, mock_cli_module)
    assert handled is True
    mock_console.print.assert_any_call("[dim]Inspired by the Gemini CLI. Powered by CrewAI & Ollama.[/dim]")

def test_handle_slash_command_help(mock_console, mock_session, mock_cli_module):
    handled = handle_slash_command("/help", ["/help"], mock_console, mock_session, mock_cli_module)
    assert handled is True
    assert mock_console.print.called
    # Check that print was called with a Panel containing Keybindings
    args, _ = mock_console.print.call_args
    panel_content = str(args[0].renderable)
    assert "Keybindings & Shortcuts" in panel_content
    assert "Alt+Enter" in panel_content
    assert "Ctrl+C" in panel_content

def test_handle_slash_command_vim_toggle(mock_console, mock_session, mock_cli_module):
    initial_mode = state.vim_mode
    handled = handle_slash_command("/vim", ["/vim"], mock_console, mock_session, mock_cli_module)
    assert handled is True
    assert state.vim_mode != initial_mode

def test_handle_slash_command_tui(mock_console, mock_session, mock_cli_module):
    handled = handle_slash_command("/tui", ["/tui"], mock_console, mock_session, mock_cli_module)
    assert handled is True
    assert mock_cli_module.run_tui_cli.called

def test_handle_slash_command_init_workspace(tmp_path, mock_console, mock_session, mock_cli_module):
    # Temporarily change directory to tmp_path to test workspace init safely
    original_dir = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        handled = handle_slash_command("/init", ["/init"], mock_console, mock_session, mock_cli_module)
        assert handled is True
        
        workspace_dir = os.path.join(tmp_path, ".nulka_cli")
        session_file = os.path.join(workspace_dir, "session.json")
        
        assert os.path.exists(workspace_dir)
        assert os.path.exists(session_file)
    finally:
        os.chdir(original_dir)

def test_handle_slash_command_cd(tmp_path, mock_console, mock_session, mock_cli_module):
    original_dir = os.getcwd()
    
    try:
        handled = handle_slash_command("/cd", ["/cd", str(tmp_path)], mock_console, mock_session, mock_cli_module)
        assert handled is True
        assert os.getcwd() == str(tmp_path)
    finally:
        os.chdir(original_dir)

def test_handle_slash_command_unknown(mock_console, mock_session, mock_cli_module):
    handled = handle_slash_command("/unknown_command_fake", ["/unknown_command_fake"], mock_console, mock_session, mock_cli_module)
    assert handled is False

def test_handle_slash_command_copy(mock_console, mock_session, mock_cli_module, monkeypatch):
    from unittest.mock import patch
    state.last_full_output = "Test Output Content"
    with patch("nulka_cli.utils.copy_text_to_clipboard", return_value=True):
        handled = handle_slash_command("/copy", ["/copy"], mock_console, mock_session, mock_cli_module)
        assert handled is True
        mock_console.print.assert_any_call("[bold green]✅ Copied last output to clipboard![/bold green]")

