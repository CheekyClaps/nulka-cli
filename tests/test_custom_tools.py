from unittest.mock import patch, MagicMock

from nulka_cli.tools.fs_tools import (
    GlobSearchTool,
    GrepSearchTool,
    ListDirectoryTool,
    ReadFileTool,
    SmartEditTool,
    WriteFileTool,
)
from nulka_cli.tools.shell_tool import RunShellCommandTool
from nulka_cli.tools.web_search_tool import WebSearchTool


@patch('nulka_cli.tools.fs_tools.ask_user_safe', return_value='y')
def test_read_write_file_tool(mock_ask, tmp_path):
    """Test creating a file and reading it back."""
    test_file = tmp_path / "test.txt"
    content = "Hello NulkaCLI!"

    writer = WriteFileTool()
    res = writer._run(str(test_file), content)
    assert "Successfully" in res

    reader = ReadFileTool()
    read_res = reader._run(str(test_file))
    assert content in read_res
    assert "<untrusted_context>" in read_res

@patch('nulka_cli.tools.fs_tools.ask_user_safe', return_value='y')
def test_replace_text_tool(mock_ask, tmp_path):
    """Test targeting string replacement."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("The old string is here.", encoding="utf-8")
    
    # Mock the chain invocation
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = "The new string is here."
    
    # The tool creates a prompt | llm pipeline, so we mock the __or__ operator
    with patch('langchain.prompts.PromptTemplate.__or__', return_value=mock_chain):
        replacer = SmartEditTool()
        res = replacer._run(str(test_file), "change old string to new string")
        assert "Successfully" in res
        
        content = test_file.read_text(encoding="utf-8")
        assert content == "The new string is here."

def test_list_directory_tool(tmp_path):
    """Test listing directory contents."""
    (tmp_path / "file1.txt").touch()
    (tmp_path / "file2.py").touch()
    
    lister = ListDirectoryTool()
    res = lister._run(str(tmp_path))
    assert "file1.txt" in res
    assert "file2.py" in res

def test_glob_search_tool(tmp_path):
    """Test finding files using glob patterns."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").touch()
    (tmp_path / "test.txt").touch()
    
    globber = GlobSearchTool()
    res = globber._run("**/*.py", str(tmp_path))
    assert "main.py" in res
    assert "test.txt" not in res

def test_grep_search_tool(tmp_path):
    """Test searching regex within files."""
    test_file = tmp_path / "config.yml"
    test_file.write_text("dummy_key: DUMMY_12345", encoding="utf-8")
    
    grepper = GrepSearchTool()
    res = grepper._run("DUMMY_.*", str(tmp_path))
    assert "config.yml" in res
    assert "dummy_key: DUMMY_12345" in res

@patch('nulka_cli.tools.shell_tool.ask_user_safe', return_value='y')
def test_run_shell_command_tool(mock_ask):
    """Test executing a basic shell command."""
    shell = RunShellCommandTool()
    res = shell._run("echo 'hello from shell'")
    assert "hello from shell" in res

def test_web_search_tool():
    """Test DDGS initialization without failure."""
    search = WebSearchTool()
    res = search._run("test query")
    assert isinstance(res, str)
