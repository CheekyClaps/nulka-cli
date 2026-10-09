import os
from unittest.mock import patch
from nulka_cli.tools.fs_tools import SearchReplaceTool

@patch('nulka_cli.tools.fs_tools.ask_user_safe', return_value='y')
def test_search_replace_single_occurrence(mock_ask, tmp_path):
    """Test successful single string replacement."""
    target_file = tmp_path / "hello.py"
    target_file.write_text("def greet():\n    return 'Hello World'\n", encoding="utf-8")

    tool = SearchReplaceTool()
    result = tool._run(
        file_path=str(target_file),
        old_string="return 'Hello World'",
        new_string="return 'Hello OpenCode & Nulka'"
    )

    assert "Successfully replaced text" in result
    updated_content = target_file.read_text(encoding="utf-8")
    assert "Hello OpenCode & Nulka" in updated_content
    assert "Hello World" not in updated_content

@patch('nulka_cli.tools.fs_tools.ask_user_safe', return_value='y')
def test_search_replace_not_found(mock_ask, tmp_path):
    """Test safe error response when target text does not exist."""
    target_file = tmp_path / "hello.py"
    target_file.write_text("alpha = 1\n", encoding="utf-8")

    tool = SearchReplaceTool()
    result = tool._run(
        file_path=str(target_file),
        old_string="beta = 2",
        new_string="beta = 3"
    )

    assert "Error: Target text not found" in result
    assert target_file.read_text(encoding="utf-8") == "alpha = 1\n"

@patch('nulka_cli.tools.fs_tools.ask_user_safe', return_value='y')
def test_search_replace_ambiguity_guardrail(mock_ask, tmp_path):
    """Test failure when target string appears multiple times without allow_multiple."""
    target_file = tmp_path / "repeat.txt"
    target_file.write_text("item: test\nitem: test\n", encoding="utf-8")

    tool = SearchReplaceTool()
    result = tool._run(
        file_path=str(target_file),
        old_string="item: test",
        new_string="item: updated",
        allow_multiple=False
    )

    assert "Error: Target text found 2 times" in result
    assert target_file.read_text(encoding="utf-8") == "item: test\nitem: test\n"

@patch('nulka_cli.tools.fs_tools.ask_user_safe', return_value='y')
def test_search_replace_allow_multiple(mock_ask, tmp_path):
    """Test successful replacement of multiple occurrences when allowed."""
    target_file = tmp_path / "repeat.txt"
    target_file.write_text("item: test\nitem: test\n", encoding="utf-8")

    tool = SearchReplaceTool()
    result = tool._run(
        file_path=str(target_file),
        old_string="item: test",
        new_string="item: updated",
        allow_multiple=True
    )

    assert "Successfully replaced text" in result
    assert target_file.read_text(encoding="utf-8") == "item: updated\nitem: updated\n"

@patch('nulka_cli.tools.fs_tools.ask_user_safe', return_value='y')
def test_search_replace_backup_creation(mock_ask, tmp_path):
    """Test that a .bak file is created prior to modification."""
    target_file = tmp_path / "critical.py"
    target_file.write_text("ORIGINAL_CONTENT\n", encoding="utf-8")

    tool = SearchReplaceTool()
    tool._run(
        file_path=str(target_file),
        old_string="ORIGINAL_CONTENT",
        new_string="MODIFIED_CONTENT"
    )

    # Check for .bak files in the directory
    bak_files = [f for f in os.listdir(tmp_path) if f.endswith(".bak")]
    assert len(bak_files) >= 1
    bak_path = tmp_path / bak_files[0]
    assert bak_path.read_text(encoding="utf-8") == "ORIGINAL_CONTENT\n"
