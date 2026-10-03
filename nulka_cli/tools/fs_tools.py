import os
import re
import fnmatch
import shutil
from pathlib import Path
from typing import Optional
from langchain.tools import BaseTool
from nulka_cli.core.state import ask_user_safe

class ReadFileTool(BaseTool):
    name: str = "read_file"
    description: str = "Reads the content of a specified file. Optionally use start_line and end_line for targeted reads."

    def _run(self, file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            start = max(0, start_line - 1) if start_line else 0
            end = end_line if end_line else len(lines)
            
            content = "".join(lines[start:end])
            # Architecture rule: context isolation
            return f"<untrusted_context>\n{content}\n</untrusted_context>"
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

    def _run(self, file_path: str, content: str, make_exec: bool = False) -> str:
        try:
            # Interactive Security Confirmation
            print(f"\n\033[93m⚠️  Agent attempting to WRITE to: {file_path}\033[0m")
            
            # Show preview of what will be written
            lines = content.split('\n')
            preview = '\n'.join(lines[:10])
            if len(lines) > 10:
                preview += f"\n... [{len(lines) - 10} more lines omitted for preview]"
            print(f"\n\033[90m--- Preview of content ---\n{preview}\n--------------------------\033[0m\n")
            
            confirm = ask_user_safe("Allow this write operation? [Y/n] ❯ ").strip().lower()
            if confirm and confirm != 'y':
                return f"Action Aborted: User denied permission to write to {file_path}."

            if not content.strip():
                return f"Safety Error: Attempted to write an empty file. If you meant to delete the file, use a shell command to remove it. Action aborted."

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

class ReplaceTextTool(BaseTool):
    name: str = "replace"
    description: str = "Replaces exact literal text within a file. Automatically creates a timestamped .bak backup."

    def _run(self, file_path: str, old_string: str, new_string: str) -> str:
        try:
            # Interactive Security Confirmation
            print(f"\n\033[93m⚠️  Agent attempting to REPLACE text in: {file_path}\033[0m")
            
            # Show preview of replacement
            lines = new_string.split('\n')
            preview = '\n'.join(lines[:5])
            if len(lines) > 5:
                preview += f"\n... [{len(lines) - 5} more lines omitted]"
            print(f"\n\033[90m--- Will replace with ---\n{preview}\n-------------------------\033[0m\n")

            confirm = ask_user_safe("Allow this replace operation? [Y/n] ❯ ").strip().lower()
            if confirm and confirm != 'y':
                return f"Action Aborted: User denied permission to replace text in {file_path}."

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if old_string not in content:
                return "Error: old_string not found in file (must be an exact match)."
                
            create_backup(file_path)
            new_content = content.replace(old_string, new_string, 1)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
                
            return f"Successfully replaced text in {file_path} (Timestamped backup saved)"
        except Exception as e:
            return f"Error replacing text: {e}"

class ListDirectoryTool(BaseTool):
    name: str = "list_directory"
    description: str = "Lists the names of files and subdirectories directly within a specified directory path."

    def _run(self, dir_path: str = ".") -> str:
        if not dir_path:
            dir_path = "."
        try:
            items = os.listdir(dir_path)
            content = "\n".join(sorted(items)) if items else "(Empty directory)"
            return f"<untrusted_context>\n{content}\n</untrusted_context>"
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
            content = "\n".join(str(p.absolute()) for p in matches[:100])
            return f"<untrusted_context>\n{content}\n</untrusted_context>"
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
                                        if len(results) >= 50: # Limit output for context safety
                                            results.append("... [Results truncated for context safety]")
                                            content = "\n".join(results)
                                            return f"<untrusted_context>\n{content}\n</untrusted_context>"
                        except (UnicodeDecodeError, PermissionError):
                            continue
                            
            content = "\n".join(results) if results else "No matches found."
            return f"<untrusted_context>\n{content}\n</untrusted_context>"
        except Exception as e:
            return f"Error running grep search: {e}"
