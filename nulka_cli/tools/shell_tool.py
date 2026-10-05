import subprocess

from langchain.tools import BaseTool

from nulka_cli.core.state import ask_user_safe


class RunShellCommandTool(BaseTool):
    name: str = "run_shell_command"
    description: str = (
        "Executes a given shell command as a subprocess. "
        "Useful for running tests, installing dependencies, or building projects."
    )

    def _run(self, command: str, dir_path: str = ".") -> str:
        """Executes the shell command.

        Args:
            command: The exact bash command to execute.
            dir_path: The directory to run the command in.
        """
        try:
            if not dir_path:
                dir_path = "."

            # Interactive Security Confirmation
            print(f"\n\033[93m⚠️  Agent attempting to RUN COMMAND in '{dir_path}':\n> {command}\033[0m")
            confirm = ask_user_safe("Allow this shell command? [Y/n] ❯ ").strip().lower()
            if confirm and confirm != 'y':
                return f"Action Aborted: User denied permission to execute command '{command}'."

            result = subprocess.run(
                command,
                cwd=dir_path,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            output = ""
            if result.stdout:
                output += f"STDOUT:\n{result.stdout}\n"
            if result.stderr:
                output += f"STDERR:\n{result.stderr}\n"
                
            if result.returncode != 0:
                output += f"\nCommand failed with return code {result.returncode}"
                
            # Truncate to protect context window
            if len(output) > 6000:
                output = output[:6000] + "\n... [Output truncated to 6000 characters]"
                
            content = output.strip() if output.strip() else "Command executed successfully with no output."
            return f"<untrusted_context>\n{content}\n</untrusted_context>"
        except subprocess.TimeoutExpired:
            return "Command execution timed out after 120 seconds."
        except Exception as e:
            return f"Error executing command: {e}"
