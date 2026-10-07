import sys
import warnings
import argparse

# Suppress Pydantic v1/v2 mixing warnings from older crewai/langchain versions
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

from nulka_cli import cli
from nulka_cli.cli import run_interactive_cli, run_tui_cli

def main():
    parser = argparse.ArgumentParser(description="NulkaCLI Enterprise Multi-Agent Workspace")
    parser.add_argument("--repl", "--classic", action="store_true", help="Launch in classic REPL mode instead of the default modern Textual TUI")
    parser.add_argument("--debug", "--verbose", action="store_true", help="Enable debug/verbose mode for agents")
    parser.add_argument("query", nargs="?", default=None, help="Optional direct query to execute headless (skips interactive loop)")
    args = parser.parse_args()

    if args.debug:
        cli.DEBUG_MODE = True

    try:
        if args.query:
            # Headless single-query execution
            run_interactive_cli(single_query=args.query)
        elif args.repl:
            # Explicit fallback to classic REPL mode
            run_interactive_cli()
        else:
            # Modern Textual TUI is the DEFAULT
            run_tui_cli()
    except KeyboardInterrupt:
        print("\nExiting. Goodbye!")
        sys.exit(0)

if __name__ == "__main__":
    main()
