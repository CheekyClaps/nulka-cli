import os
import re
import select
import signal
import subprocess
import time

from langchain.tools import BaseTool

from nulka_cli.core.state import ask_user_safe


class RunShellCommandTool(BaseTool):
    name: str = "run_shell_command"
    description: str = (
        "Executes a given shell command in a pseudo-terminal (PTY) environment with real-time streaming. "
        "Useful for running tests, build tools, package managers, and system administration tasks."
    )

    def _execute_pty(self, command: str, dir_path: str, state) -> tuple[int, str]:
        """Executes the command inside a POSIX pseudo-terminal (PTY)."""
        master, slave = os.openpty()
        try:
            proc = subprocess.Popen(
                command,
                cwd=dir_path,
                shell=True,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                close_fds=True,
                preexec_fn=os.setsid
            )
        except Exception as e:
            os.close(slave)
            os.close(master)
            raise e

        os.close(slave)

        collected_chunks = []
        line_buffer = ""
        start_time = time.time()

        try:
            while True:
                if time.time() - start_time > 120:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except Exception:
                        proc.kill()
                    state.stream_line("[bold red]❌ Command execution timed out after 120 seconds.[/]")
                    raise subprocess.TimeoutExpired(cmd=command, timeout=120)

                r, _, _ = select.select([master], [], [], 0.05)
                if r:
                    try:
                        data = os.read(master, 2048)
                        if not data:
                            break
                        decoded = data.decode("utf-8", errors="replace")
                        collected_chunks.append(decoded)
                        line_buffer += decoded
                        while "\n" in line_buffer:
                            line, line_buffer = line_buffer.split("\n", 1)
                            state.stream_line(line.replace("\r", ""))
                    except OSError:
                        # Slave closed on child exit (EIO)
                        break

                if proc.poll() is not None and not select.select([master], [], [], 0)[0]:
                    break

            if line_buffer.strip():
                state.stream_line(line_buffer.replace("\r", ""))
        finally:
            try:
                os.close(master)
            except Exception:
                pass

        returncode = proc.wait(timeout=5)
        full_output = "".join(collected_chunks).strip()
        return returncode, full_output

    def _execute_pipe(self, command: str, dir_path: str, state) -> tuple[int, str]:
        """Fallback execution using standard pipes when PTY is unavailable."""
        proc = subprocess.Popen(
            command,
            cwd=dir_path,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        collected_lines = []
        try:
            for line in iter(proc.stdout.readline, ''):
                collected_lines.append(line)
                state.stream_line(line.rstrip('\r\n'))
            proc.stdout.close()
            returncode = proc.wait(timeout=120)
        except subprocess.TimeoutExpired:
            proc.kill()
            state.stream_line("[bold red]❌ Command execution timed out after 120 seconds.[/]")
            raise subprocess.TimeoutExpired(cmd=command, timeout=120)

        full_output = "".join(collected_lines).strip()
        return returncode, full_output

    def _run(self, command: str, dir_path: str = ".") -> str:
        """Executes the shell command with PTY terminal emulation and live Action Drawer streaming.

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
                return f"Action Aborted by User: You MUST NOT retry this command. Do not add sudo. Stop immediately and explain to the user that the action was cancelled."

            from nulka_cli.core.state import state

            # Notify stream listener of command start
            state.stream_line(f"[bold cyan]❯ Running:[/] [green]{command}[/]")

            # Choose PTY on POSIX systems with openpty support, fallback to standard pipes otherwise
            use_pty = os.name == 'posix' and hasattr(os, 'openpty')
            if use_pty:
                try:
                    returncode, full_output = self._execute_pty(command, dir_path, state)
                except Exception:
                    returncode, full_output = self._execute_pipe(command, dir_path, state)
            else:
                returncode, full_output = self._execute_pipe(command, dir_path, state)

            state.last_full_output = full_output

            status_msg = f"[Process completed with return code {returncode}]"
            state.stream_line(f"[dim]{status_msg}[/dim]")

            # Clean ANSI escape sequences for LLM context while preserving them for UI display
            plain_output = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', full_output)

            # Condense output for LLM context window if voluminous
            lines = plain_output.split("\n") if plain_output else []
            if len(lines) > 35:
                first_lines = "\n".join(lines[:15])
                last_lines = "\n".join(lines[-15:])
                condensed = (
                    f"{first_lines}\n\n"
                    f"... [{len(lines) - 30} lines condensed to save context. Use /expand to view full logs] ...\n\n"
                    f"{last_lines}"
                )
            else:
                condensed = plain_output if plain_output else "Command executed successfully with no output."

            if returncode != 0:
                condensed += f"\nCommand failed with return code {returncode}"

            return f"<untrusted_context>\n{condensed}\n</untrusted_context>"
        except subprocess.TimeoutExpired:
            return "Command execution timed out after 120 seconds."
        except Exception as e:
            return f"Error executing command: {e}"
