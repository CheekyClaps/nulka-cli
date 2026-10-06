import fnmatch
import os
import re
import shutil
import sys
import difflib
from pathlib import Path

from langchain.tools import BaseTool
from rich.console import Console
from rich.markup import escape

from nulka_cli.core.state import ask_user_safe

console = Console(file=sys.__stdout__)

def print_bypass(text: str):
    try:
        sys.__stdout__.write(text + "\n")
        sys.__stdout__.flush()
    except Exception:
        print(text)

def show_in_pager(content: str, title: str, lexer: str = None):
    """Displays massive content blocks safely using Rich's built in pager."""
    with console.pager(styles=True):
        console.print(f"[bold cyan]--- {escape(title)} ---[/]\n")
        if lexer:
            from rich.syntax import Syntax
            console.print(Syntax(content, lexer, theme="monokai", word_wrap=True))
        else:
            console.print(content)


class ReadFileTool(BaseTool):
    name: str = "read_file"
    description: str = "Reads the content of a specified file. Optionally use start_line and end_line for targeted reads."

    def _run(self, file_path: str, start_line: int | None = None, end_line: int | None = None) -> str:
        try:
            file_path = os.path.expanduser(file_path)
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            start = max(0, start_line - 1) if start_line else 0
            end = end_line if end_line else len(lines)

            max_lines = 1000
            truncated = False

            if (end - start) > max_lines:
                end = start + max_lines
                truncated = True

            content = "".join(lines[start:end])

            result = f"<untrusted_context>\n{content}\n&lt;/untrusted_context&gt;"

            if truncated:
                result += f"\n\n[SYSTEM WARNING]: File truncated at {max_lines} lines to protect context window. To read more, you MUST use the `start_line` and `end_line` parameters."

            return result
        except Exception as e:
            return f"Error reading file: {e}"

import datetime


def create_backup(file_path: str) -> None:
    """Helper to create a timestamped .bak copy of a file before modifying it."""
    if os.path.exists(file_path):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{file_path}.{timestamp}.bak"
        shutil.copy2(file_path, backup_path)

class WriteFileTool(BaseTool):
    name: str = "write_file"
    description: str = "Writes the COMPLETE, fully functional content to a file, creating missing parent directories. Overwrites existing files. Automatically creates a timestamped .bak backup. Rejects writing empty strings to non-empty files. You MUST NOT use placeholders like 'Your code goes here' or omit code. The 'content' argument MUST contain the entire literal file contents."

    def _run(self, file_path: str, content: str = "", make_exec: bool = False, new_content: str = "") -> str:
        content = content or new_content
        if not content:
            return "Error: You must provide the 'content' argument containing the file data."
        try:
            file_path = os.path.expanduser(file_path)
            print_bypass(f"\n\033[93m⚠️  Agent attempting to WRITE to: {file_path}\033[0m")
            
            while True:
                # Show preview of what will be written
                lines = content.split('\n')
                preview = '\n'.join(lines[:10])
                if len(lines) > 10:
                    preview += f"\n... [{len(lines) - 10} more lines omitted for preview]"

                filename = os.path.basename(file_path)
                ext = os.path.splitext(file_path)[1].lstrip('.')
                lexer_name = ext if ext else filename

                console.print("\n[bold cyan]--- Preview of content ---[/]")
                from rich.syntax import Syntax
                console.print(Syntax(preview, lexer_name, theme="monokai", word_wrap=True))
                console.print("[bold cyan]--------------------------[/]\n")

                confirm = ask_user_safe("Allow this write operation? [Y/n/v(view)] ❯ ").strip().lower()
                if confirm == 'v':
                    show_in_pager(content, f"Full Payload for {file_path}", lexer=lexer_name)
                    continue
                elif confirm and confirm != 'y':
                    feedback = ask_user_safe("Provide feedback to the agent (leave blank to cancel completely) ❯ ").strip()
                    if feedback:
                        return f"Action Aborted: User denied permission. User Feedback: {feedback}"
                    else:
                        return f"Action Aborted: User denied permission to write to {file_path}. DO NOT RETRY. The user has cancelled this operation."
                break

            if not content.strip():
                return "Safety Error: Attempted to write an empty file. If you meant to delete the file, use a shell command to remove it. Action aborted."

            # Safety check against accidental 0-byte truncation of existing files
            if os.path.exists(file_path):
                original_size = os.path.getsize(file_path)
                new_size = len(content)
                
                # Heuristic: If we are shrinking a file by more than 80% and the original was > 150 bytes, it's likely a lazy LLM placeholder truncation.
                if original_size > 150 and new_size < (original_size * 0.2):
                     return f"Validation Error: Drastic size reduction detected (Original: {original_size} bytes, New: {new_size} bytes). This usually indicates you used a placeholder instead of writing the full file. You MUST write the ENTIRE, fully functional file content. Action aborted."
                
                create_backup(file_path)
                
            # Strict safety check against LLM placeholders
            placeholder_patterns = [
                "your shell script content", "your script content", "goes here", 
                "rest of the code", "rest of your code", "your code goes here", 
                "omitted for brevity", "unchanged code", "your logic here", 
                "your actual script", "insert code here", "insert your code",
                "remaining code", "complete sh script content", "content here",
                "full script here"
            ]
            content_lower = content.lower()
            for pattern in placeholder_patterns:
                if pattern in content_lower:
                    return f"Validation Error: The content appears to contain a placeholder ('{pattern}'). You MUST write the ENTIRE, fully functional file content. Do not use placeholders or omit code. Action aborted."

            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            if make_exec:
                os.chmod(file_path, 0o755)
                return f"Successfully wrote and made executable: {file_path} (Backup saved as .bak)"
                
            return f"Successfully wrote to {file_path} (Backup saved as .bak)"
        except Exception as e:
            return f"Error writing file: {e}"

class SmartEditTool(BaseTool):
    name: str = "smart_edit"
    description: str = "Replaces or modifies text within an existing file. REQUIRED for targeted edits. Arguments: 'file_path' (string) and 'instruction' (string detailing the change). You MUST INVOKE THIS TOOL to apply your changes; do NOT simply explain what you would do. However, if you determine NO changes are needed after reading the file, DO NOT invoke this tool; simply state that the file is already up to date in your final answer."

    def _run(self, file_path: str, instruction: str = "", new_content: str = "") -> str:
        instruction = instruction or new_content
        if not instruction:
            return "Error: You must provide an 'instruction' argument detailing what to change."
        try:
            file_path = os.path.expanduser(file_path)
            if not os.path.exists(file_path):
                return f"Error: File {file_path} does not exist."

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            print_bypass(f"\n\033[93m⚠️  Agent attempting to SMART-EDIT: {file_path}\033[0m")
            print_bypass(f"\033[90m--- Instruction ---\n{instruction}\n-------------------\033[0m\n")
            print_bypass("\033[90m[Interpretation Layer: Processing edit with local LLM...]\033[0m")

            # Import the local LLM dynamically to avoid circular dependencies
            from langchain.prompts import PromptTemplate
            from nulka_cli.utils import ollama_llm
            
            prompt = PromptTemplate(
                input_variables=["instruction", "content"],
                template=(
                    "You are a strict code editing machine. You will be given an existing file and an instruction. "
                    "You must output the ENTIRE modified file content. "
                    "Do NOT output any conversational text whatsoever. Do NOT use placeholders like 'rest of code'. "
                    "Output ONLY the new file content exactly as it should be written, wrapped inside a SINGLE Markdown block (e.g. ```\n... \n```).\n\n"
                    "INSTRUCTION:\n{instruction}\n\n"
                    "FILE CONTENT:\n{content}"
                )
            )
            
            chain = prompt | ollama_llm
            response = chain.invoke({"instruction": instruction, "content": content})
            
            # Extract content from markdown block if present
            new_content = response
            block_match = re.search(r'```[a-zA-Z]*\n(.*?)```', response, re.DOTALL)
            if block_match:
                new_content = block_match.group(1).strip('\n')
            else:
                new_content = new_content.strip('\n')
                
            # Basic sanity check
            if not new_content or (len(new_content) < len(content) * 0.15 and len(content) > 150):
                return "Error: Internal LLM failed to generate a valid replacement (suspected placeholder output). Action aborted."
                
            if len(content) == 0 and "please provide" in new_content.lower():
                return "Error: Target file was empty, and the LLM refused to edit it. If creating a new file, use write_file instead."

            # Generate diff
            diff = list(difflib.unified_diff(
                content.splitlines(),
                new_content.splitlines(),
                fromfile='Original',
                tofile='Modified',
                lineterm=''
            ))

            if not diff:
                console.print("\n[bold yellow]⚠ Smart Edit resulted in no changes to the file. Skipping user confirmation.[/]\n")
                return "No changes were made. The file content is already identical to the requested changes. Do not retry; please proceed with your final answer."

            diff_text = '\n'.join(diff)

            preview_lines = diff[:15]
            if len(diff) > 15:
                preview_lines.append(f"... [{len(diff) - 15} more lines omitted for preview]")
            preview = '\n'.join(preview_lines)

            console.print("\n[bold cyan]--- Diff Preview ---[/]")
            from rich.syntax import Syntax
            console.print(Syntax(preview, "diff", theme="monokai", word_wrap=True))
            console.print("[bold cyan]--------------------[/]\n")

            while True:
                confirm = ask_user_safe("Allow this edit operation? [Y/n/v(view diff)] ❯ ").strip().lower()
                if confirm == 'v':
                    show_in_pager(diff_text, f"Full Diff for {file_path}", lexer="diff")
                    continue
                elif confirm and confirm != 'y':
                    feedback = ask_user_safe("Provide feedback to the agent (leave blank to cancel completely) ❯ ").strip()
                    if feedback:
                        return f"Action Aborted: User denied permission. User Feedback: {feedback}"
                    else:
                        return f"Action Aborted: User denied permission to edit {file_path}. DO NOT RETRY. The user has cancelled this operation."
                break

            create_backup(file_path)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
                
            return f"Successfully applied smart edit to {file_path} (Timestamped backup saved)"
        except Exception as e:
            return f"Error executing smart edit: {e}"

class ListDirectoryTool(BaseTool):
    name: str = "list_directory"
    description: str = "Lists the names of files and subdirectories directly within a specified directory path."

    def _run(self, dir_path: str = ".") -> str:
        if not dir_path:
            dir_path = "."
        try:
            items = sorted(os.listdir(dir_path))
            max_items = 500
            truncated = len(items) > max_items
            items = items[:max_items]

            content = "\n".join(items) if items else "(Empty directory)"
            result = f"<untrusted_context>\n{content}\n&lt;/untrusted_context&gt;"
            if truncated:
                result += f"\n\n[SYSTEM WARNING]: Output truncated at {max_items} items to protect context window."
            return result
        except Exception as e:
            return f"Error listing directory: {e}"

class GlobSearchTool(BaseTool):
    name: str = "glob"
    description: str = "Efficiently finds files matching specific glob patterns (e.g., 'src/**/*.py')."

    def _run(self, pattern: str, dir_path: str = ".") -> str:
        try:
            path = Path(dir_path)
            if not path.exists():
                return f"Error: Directory '{dir_path}' does not exist."
            matches = list(path.rglob(pattern))
            if not matches:
                return "No files matched the pattern."

            max_items = 200
            truncated = len(matches) > max_items
            matches = matches[:max_items]

            content = "\n".join(str(p.absolute()) for p in matches)
            result = f"<untrusted_context>\n{content}\n&lt;/untrusted_context&gt;"
            if truncated:
                result += f"\n\n[SYSTEM WARNING]: Output truncated at {max_items} matches to protect context window."
            return result
        except Exception as e:
            return f"Error running glob search: {e}"

class GrepSearchTool(BaseTool):
    name: str = "grep_search"
    description: str = "Searches for a regular expression pattern within file contents across a directory."

    def _run(self, pattern: str, dir_path: str = ".", include_pattern: str = "*") -> str:
        results = []
        try:
            compiled_pattern = re.compile(pattern)
            for root, _, files in os.walk(dir_path):
                # Skip common ignore directories
                if any(ignored in root for ignored in ['.git', '__pycache__', 'venv', 'node_modules']):
                    continue
                    
                for filename in files:
                    if fnmatch.fnmatch(filename, include_pattern):
                        filepath = os.path.join(root, filename)
                        try:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                for i, line in enumerate(f):
                                    if compiled_pattern.search(line):
                                        results.append(f"{filepath}:{i+1}: {line.strip()}")
                                        if len(results) >= 200:
                                            content = "\n".join(results)
                                            result = f"<untrusted_context>\n{content}\n&lt;/untrusted_context&gt;"
                                            result += "\n\n[SYSTEM WARNING]: Output truncated at 200 matches to protect context window."
                                            return result
                        except (UnicodeDecodeError, PermissionError):
                            continue
                            
            content = "\n".join(results) if results else "No matches found."
            return f"<untrusted_context>\n{content}\n</untrusted_context>"
        except Exception as e:
            return f"Error running grep search: {e}"
