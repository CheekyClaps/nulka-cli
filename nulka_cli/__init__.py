import json

import regex
from crewai.agents.tools_handler import ToolsHandler
from crewai.tools.tool_output_parser import ToolOutputParser
from crewai.utilities.printer import Printer
from rich.console import Console
from rich.panel import Panel

console = Console()

# Monkey-patch crewai Printer to colorize tool outputs uniquely
original_print = Printer.print

def _patched_print(self, content: str, color: str):
    if color == "yellow":
        # CrewAI uses yellow for tool results. Let's make it a distinct panel.
        # Check if it looks like a tool result
        clean_content = content.strip()
        if clean_content:
            console.print(Panel(f"[dim cyan]{clean_content}[/dim cyan]", title="🔧 [bold cyan]Tool Output[/bold cyan]", border_style="cyan"))
    else:
        # Default behavior for other prints
        original_print(self, content, color)

Printer.print = _patched_print

# Monkey-patch crewai ToolsHandler to colorize tool invocation uniquely
original_on_tool_use = ToolsHandler.on_tool_use

def _patched_on_tool_use(self, calling, output: str):
    console.print(f"\n⚙️  [bold magenta]Agent Executing Tool:[/bold magenta] [white]{calling.tool_name}[/white]")
    return original_on_tool_use(self, calling, output)

ToolsHandler.on_tool_use = _patched_on_tool_use

# Monkey-patch crewai ToolOutputParser to handle bad JSON escapes and prevent string exception crashes
original_transform = ToolOutputParser._transform_in_valid_json

def _patched_transform_in_valid_json(self, text) -> str:
    text = text.replace("```", "").replace("json", "")
    json_pattern = r"\{(?:[^{}]|(?R))*\}"
    matches = regex.finditer(json_pattern, text)

    for match in matches:
        try:
            # Replace invalid JSON escapes like \. with \\. before parsing
            matched_str = match.group()
            # simple cleanup for common llm escaping errors in regex patterns
            matched_str = regex.sub(r'\\([^"\\/bfnrt])', r'\\\\\1', matched_str)
            
            json_obj = json.loads(matched_str, strict=False)
            json_obj = json.dumps(json_obj)
            return str(json_obj)
        except json.JSONDecodeError:
            continue
    return text

ToolOutputParser._transform_in_valid_json = _patched_transform_in_valid_json
