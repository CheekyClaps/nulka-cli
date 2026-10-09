from unittest.mock import MagicMock, patch
import pytest
from nulka_cli import main
from nulka_cli.cli import run_tui_cli
from nulka_cli.ui.tui_app import NulkaApp

def test_main_defaults_to_tui(monkeypatch):
    """Verify that launching nulka_cli without args defaults to run_tui_cli."""
    tui_called = False

    def mock_run_tui():
        nonlocal tui_called
        tui_called = True

    monkeypatch.setattr("nulka_cli.main.run_tui_cli", mock_run_tui)
    monkeypatch.setattr("sys.argv", ["nulka_cli"])

    main.main()
    assert tui_called is True

def test_main_repl_flag_fallback(monkeypatch):
    """Verify that --repl or --classic flag falls back to run_interactive_cli."""
    interactive_called = False

    def mock_run_interactive(single_query=None):
        nonlocal interactive_called
        interactive_called = True

    monkeypatch.setattr("nulka_cli.main.run_interactive_cli", mock_run_interactive)
    monkeypatch.setattr("sys.argv", ["nulka_cli", "--repl"])

    main.main()
    assert interactive_called is True

def test_main_single_query_headless(monkeypatch):
    """Verify that providing a positional query argument executes headless."""
    received_query = None

    def mock_run_interactive(single_query=None):
        nonlocal received_query
        received_query = single_query

    monkeypatch.setattr("nulka_cli.main.run_interactive_cli", mock_run_interactive)
    monkeypatch.setattr("sys.argv", ["nulka_cli", "test single query"])

    main.main()
    assert received_query == "test single query"
