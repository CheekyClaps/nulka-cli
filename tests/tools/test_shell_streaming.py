from unittest.mock import patch
from nulka_cli.tools.shell_tool import RunShellCommandTool
from nulka_cli.core.state import state

@patch('nulka_cli.tools.shell_tool.ask_user_safe', return_value='y')
def test_shell_command_streaming(mock_ask):
    """Test that RunShellCommandTool dispatches lines to state.stream_listener in real time."""
    streamed_lines = []
    
    def mock_listener(line: str):
        streamed_lines.append(line)

    state.set_stream_listener(mock_listener)
    try:
        tool = RunShellCommandTool()
        result = tool._run("echo 'line one' && echo 'line two'")
        
        assert "line one" in result
        assert "line two" in result
        assert any("line one" in line for line in streamed_lines)
        assert any("line two" in line for line in streamed_lines)
        assert any("Running:" in line for line in streamed_lines)
    finally:
        state.set_stream_listener(None)

@patch('nulka_cli.tools.shell_tool.ask_user_safe', return_value='y')
def test_shell_command_output_condensation(mock_ask):
    """Test that outputs with > 35 lines are condensed for the LLM context."""
    tool = RunShellCommandTool()
    # Generate 50 lines of output
    cmd = "python3 -c \"for i in range(50): print(f'item_{i}')\""
    result = tool._run(cmd)

    assert "<untrusted_context>" in result
    assert "lines condensed to save context" in result
    assert "item_0" in result
    assert "item_49" in result
    # Middle lines should be omitted from the LLM prompt
    assert "item_25" not in result
    
    # But state.last_full_output should still contain everything
    assert "item_25" in state.last_full_output
