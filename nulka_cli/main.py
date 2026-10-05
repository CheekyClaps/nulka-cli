import sys
import warnings
import argparse

# Suppress Pydantic v1/v2 mixing warnings from older crewai/langchain versions
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

from nulka_cli import cli
from nulka_cli.cli import run_interactive_cli

def main():
    parser = argparse.ArgumentParser(description="NulkaCLI Enterprise Multi-Agent Workspace")
    parser.add_argument("--debug", "--verbose", action="store_true", help="Enable debug/verbose mode for agents")
    parser.add_argument("query", nargs="?", default=None, help="Optional direct query to execute (skips interactive loop)")
    args = parser.parse_args()

    if args.debug:
        cli.DEBUG_MODE = True

    try:
        run_interactive_cli(single_query=args.query)
    except KeyboardInterrupt:
        print("\nExiting. Goodbye!")
        sys.exit(0)

if __name__ == "__main__":
    main()
