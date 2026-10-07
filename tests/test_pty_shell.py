from unittest.mock import patch
import pytest
from nulka_cli.tools.shell_tool import RunShellCommandTool
from nulka_cli.core.state import state

@patch('nulka_cli.tools.shell_tool.ask_user_safe', return_value='y')
def test_shell_pty_isatty(mock_ask):
    """Test that commands executed by RunShellCommandTool run in a genuine TTY."""
    tool = RunShellCommandTool()
    cmd = "python3 -c \"import sys; print('IS_TTY:', sys.stdout.isatty())\""
    result = tool._run(cmd)

    assert "<untrusted_context>" in result
    assert "IS_TTY: True" in result

@patch('nulka_cli.tools.shell_tool.ask_user_safe', return_value='y')
def test_shell_pty_returncode_and_output(mock_ask):
    """Test that return code and stdout/stderr are captured through PTY."""
    tool = RunShellCommandTool()
    result = tool._run("echo 'Hello PTY'; exit 3")

    assert "Hello PTY" in result
    assert "Command failed with return code 3" in result

@patch('nulka_cli.tools.shell_tool.ask_user_safe', return_value='y')
def test_shell_pty_ansi_stripping_for_llm(mock_ask):
    """Test that ANSI escape sequences are stripped from LLM return string."""
    tool = RunShellCommandTool()
    cmd = "python3 -c \"print('\\x1b[31mRed Text\\x1b[0m')\""
    result = tool._run(cmd)

    assert "Red Text" in result
    # Escape sequence should be stripped in the LLM context string
    assert "\x1b[31m" not in result
    assert "\x1b[0m" not in result

@patch('nulka_cli.tools.shell_tool.ask_user_safe', return_value='y')
def test_shell_pipe_fallback(mock_ask, monkeypatch):
    """Test fallback to _execute_pipe when PTY is mocked as unavailable."""
    monkeypatch.setattr("os.name", "nt") # Simulate non-posix environment
    
    tool = RunShellCommandTool()
    result = tool._run("echo 'Fallback mode'")

    assert "Fallback mode" in result
