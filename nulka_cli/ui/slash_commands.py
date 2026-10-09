import os
import sys

from rich.markup import escape

from nulka_cli.core.state import state
from nulka_cli.hrf_manager import hrf_manager


# Inline implementation to avoid circular dependencies
def get_active_model_name() -> str:
    from nulka_cli.utils import ollama_llm
    return ollama_llm.model

# Note: console, execute_teach_feedback, execute_expand_pager are imported/passed where needed
# to avoid massive circular imports, we will keep the heavy lifting in cli.py or pass callables.

def handle_slash_command(cmd: str, parts: list[str], console, session, cli_module) -> bool:
    """
    Handles slash commands for the interactive CLI.
    Returns True if the command was handled (meaning the loop should `continue`).
    Returns False if it was not a handled slash command (or unknown).
    """
    
    # 1. Core Session & Environment
    if cmd in ["/help", "/?", "/commands"]:
        print_help(console)
        return True
    elif cmd == "/about":
        console.print("[bold green]NulkaCLI[/bold green] - A robust, production-ready omni-agent CLI.")
        console.print("[dim]Inspired by the Gemini CLI. Powered by CrewAI & Ollama.[/dim]")
        return True
    elif cmd == "/clear":
        os.system('clear' if os.name == 'posix' else 'cls')
        if hasattr(session.history, 'clear'):
            # Some prompt_toolkit histories don't support direct clear, but we do our best
            try: session.history.clear()
            except: pass
        state.last_user_prompt = None
        state.last_full_output = None
        console.print("[bold green]✨ Screen and session context cleared.[/bold green]")
        return True
    elif cmd == "/vim":
        state.vim_mode = not state.vim_mode
        status = "[bold green]ON[/bold green]" if state.vim_mode else "[bold red]OFF[/bold red]"
        console.print(f"⌨️  [bold]Vim Mode:[/bold] {status}")
        return True
    elif cmd == "/tui":
        console.print("[bold cyan]🚀 Switching to Modern Textual TUI Mode...[/bold cyan]")
        cli_module.run_tui_cli()
        return True
    elif cmd in ["/quit", "/exit"]:
        if "--delete" in parts:
            history_file = os.path.join(os.path.expanduser("~"), ".nulka_cli_history")
            if os.path.exists(history_file):
                os.remove(history_file)
            console.print("[bold red]🗑️ History purged.[/bold red]")
        console.print("[bold yellow]Goodbye human[/bold yellow]")
        sys.exit(0)

    # 2. Tools & Agents Inspection
    elif cmd == "/tools":
        from rich.table import Table
        from rich import box
        table = Table(box=box.ROUNDED, show_lines=True, padding=(0, 2))
        table.add_column("Tool Name", style="bold cyan")
        table.add_column("Description", style="white")
        table.add_row("read_file", "Read file contents.")
        table.add_row("write_file", "Write to files.")
        table.add_row("replace", "Precise file text replacement.")
        table.add_row("list_directory", "List files in a directory.")
        table.add_row("glob", "Glob search files (e.g. **/*.py).")
        table.add_row("grep_search", "Regex content search.")
        table.add_row("run_shell_command", "Execute bash shell commands.")
        table.add_row("web_fetch / web_search", "Web interaction tools.")
        table.add_row("consult_oracle", "Fallback to universal truth (gemini/claude).")

        console.print(table)
        return True
    elif cmd == "/agents":
        from nulka_cli.utils import load_agent_configs
        from rich.table import Table
        from rich import box
        
        configs = load_agent_configs()
        table = Table(box=box.ROUNDED, show_lines=True, padding=(1, 2))
        table.add_column("Agent", style="bold green", no_wrap=True)
        table.add_column("Role", style="bold yellow")
        table.add_column("Description / Goal", style="white")
        
        for key, conf in configs.items():
            name = key.replace("_", " ").title()
            role = conf.get("role", "").strip()
            goal = conf.get("goal", "").strip()
            table.add_row(name, role, goal)
            
        console.print(table)
        return True
    
    # 3. Output Management
    elif cmd == "/copy":
        if not state.last_full_output:
            console.print("[bold red]❌ No recent output to copy.[/bold red]")
            return True
        from nulka_cli.utils import copy_text_to_clipboard
        if copy_text_to_clipboard(state.last_full_output):
            console.print("[bold green]✅ Copied last output to clipboard![/bold green]")
        else:
            console.print("[bold yellow]⚠️ Unable to copy to clipboard automatically.[/bold yellow]")
            console.print("[dim]Please ensure wl-copy, xsel, or xclip is installed, or hold Shift to select text.[/dim]")
        return True
    elif cmd in ["/copy_log", "/copy_logs", "/copylog", "/copylogs"]:
        import re
        from nulka_cli.utils import copy_text_to_clipboard
        ansi_escape = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
        log_text = ""
        if hasattr(session, "action_log_buffer"):
            clean_action = ansi_escape.sub('', getattr(session, "action_log_buffer", "")).strip()
            clean_thought = ansi_escape.sub('', getattr(session, "thought_log_buffer", "")).strip()
            if clean_action:
                log_text += f"=== ACTION STREAM ===\n{clean_action}\n\n"
            if clean_thought:
                log_text += f"=== MODEL THOUGHTS ===\n{clean_thought}\n\n"
        
        if not log_text and state.last_full_output:
            log_text = state.last_full_output

        if not log_text:
            console.print("[bold red]❌ No stream logs or outputs found to copy.[/bold red]")
            return True

        if copy_text_to_clipboard(log_text.strip()):
            console.print("[bold green]✅ Copied stream logs to clipboard![/bold green]")
        else:
            console.print("[bold yellow]⚠️ Unable to copy logs to clipboard automatically.[/bold yellow]")
            console.print("[dim]Please ensure wl-copy, xsel, or xclip is installed.[/dim]")
        return True
    elif cmd == "/expand":
        cli_module.execute_expand_pager()
        return True
        
    # 4. Workspace & Directory
    elif cmd == "/init":
        workspace_dir = os.path.join(os.path.abspath(os.getcwd()), ".nulka_cli")
        if os.path.exists(workspace_dir):
            console.print(f"[bold yellow]⚠️ Workspace already initialized at {escape(workspace_dir)}[/bold yellow]")
        else:
            try:
                os.makedirs(workspace_dir)
                with open(os.path.join(workspace_dir, "session.json"), "w", encoding="utf-8") as f:
                    f.write('{"history": []}')
                console.print(f"[bold green]✅ Successfully initialized NulkaCLI workspace at {escape(workspace_dir)}[/bold green]")
                console.print("[dim]Session progress and workspace memory will now be persistently saved here.[/dim]")
            except Exception as e:
                console.print(f"❌ Failed to initialize workspace: {e}", style="bold red", markup=False)
        return True
    elif cmd == "/cd":
        target_dir = os.path.expanduser(" ".join(parts[1:]) if len(parts) > 1 else "~")
        target_dir = os.path.abspath(target_dir)
        if not os.path.exists(target_dir):
            console.print(f"[bold red]❌ Directory does not exist: {escape(target_dir)}[/bold red]")
        elif not os.path.isdir(target_dir):
            console.print(f"[bold red]❌ Path is not a directory: {escape(target_dir)}[/bold red]")
        else:
            try:
                os.chdir(target_dir)
                if target_dir not in state.active_workspace_dirs:
                    state.active_workspace_dirs.append(target_dir)
                console.print(f"[bold green]✅ Changed working directory to:[/] [cyan]{escape(target_dir)}[/cyan]")
            except Exception as e:
                console.print(f"❌ Failed to change directory: {e}", style="bold red", markup=False)
        return True
    elif cmd == "/pwd":
        console.print(f"📂 [bold]Current Working Directory:[/bold] [cyan]{escape(os.getcwd())}[/cyan]")
        return True
    elif cmd in ["/ls", "/list"]:
        target_dir = os.path.expanduser(" ".join(parts[1:]) if len(parts) > 1 else ".")
        target_dir = os.path.abspath(target_dir)
        if not os.path.exists(target_dir):
            console.print(f"[bold red]❌ Path does not exist: {escape(target_dir)}[/bold red]")
            return True
        if not os.path.isdir(target_dir):
            console.print(f"[bold red]❌ Path is not a directory: {escape(target_dir)}[/bold red]")
            return True
        try:
            items = sorted(os.listdir(target_dir))
            if not items:
                console.print("[dim]Directory is empty.[/dim]")
                return True
            
            # Format nicely: Directories first, then files
            dirs = []
            files = []
            for item in items:
                # Ignore hidden files by default unless asked, or just show them
                full_path = os.path.join(target_dir, item)
                if os.path.isdir(full_path):
                    dirs.append(item)
                else:
                    files.append(item)
            
            console.print(f"📂 [bold]Listing directory:[/bold] [cyan]{escape(target_dir)}[/cyan]")
            for d in dirs:
                console.print(f"  [bold blue]📁 {escape(d)}/[/bold blue]")
            for f in files:
                console.print(f"  📄 {escape(f)}")
        except Exception as e:
            console.print(f"❌ Failed to list directory: {e}", style="bold red", markup=False)
        return True
    elif cmd in ["/dir", "/directory", "/workspace"]:
        subcmd = parts[1].lower() if len(parts) > 1 else "show"
        if subcmd == "show":
            console.print("[bold yellow]📂 Active Workspace Directories:[/bold yellow]")
            for d in state.active_workspace_dirs:
                active_marker = " [bold green](Current)[/bold green]" if d == os.getcwd() else ""
                console.print(f"  ➔ [cyan]{escape(d)}[/cyan]{active_marker}")
        elif subcmd == "add" and len(parts) >= 3:
            for p in " ".join(parts[2:]).split(","):
                p_exp = os.path.abspath(os.path.expanduser(p.strip()))
                if os.path.isdir(p_exp) and p_exp not in state.active_workspace_dirs:
                    state.active_workspace_dirs.append(p_exp)
                    console.print(f"[bold green]✅ Added to workspace:[/bold green] [cyan]{escape(p_exp)}[/cyan]")
        elif subcmd in ["set", "cd"] and len(parts) >= 3:
            handle_slash_command("/cd", ["/cd"] + parts[2:], console, session, cli_module)
        else:
            console.print("[bold red]❌ Usage: /workspace [show|add <paths>|set <path>][/bold red]")
        return True

    # 5. Core Display & Debug
    elif cmd == "/metrics":
        state.show_metrics = not state.show_metrics
        status = "[bold green]ON[/bold green]" if state.show_metrics else "[bold red]OFF[/bold red]"
        console.print(f"📊 [bold]Metrics Toolbar:[/bold] {status}")
        return True
    elif cmd == "/debug":
        cli_module.DEBUG_MODE = not cli_module.DEBUG_MODE
        status = "[bold green]ON[/bold green]" if cli_module.DEBUG_MODE else "[bold red]OFF[/bold red]"
        console.print(f"⚙️  [bold]Debug Mode (Verbose Agent Thoughts):[/bold] {status}")
        return True

    # 6. Model Management
    elif cmd == "/models":
        table_content = cli_module.show_ollama_models()
        # Print directly to chat feed to allow easy text selection/copying
        if isinstance(table_content, str):
            console.print(table_content)
        else:
            console.print(table_content)
        return True
    elif cmd == "/pull":
        if len(parts) < 2:
            console.print("[bold red]❌ Usage: /pull <model_name>[/]")
        else:
            cli_module.pull_ollama_model(parts[1])
        return True
    elif cmd == "/load":
        if len(parts) < 2:
            console.print("[bold red]❌ Usage: /load <model_name>[/]")
        else:
            cli_module.load_ollama_model(parts[1])
        return True
    elif cmd == "/stop":
        if len(parts) < 2:
            console.print("[bold red]❌ Usage: /stop <model_name>[/]")
        else:
            cli_module.stop_ollama_model(parts[1])
        return True
    elif cmd == "/rm":
        if len(parts) < 2:
            console.print("[bold red]❌ Usage: /rm <model_name>[/]")
        else:
            cli_module.remove_ollama_model(parts[1])
        return True
        
    # 7. HRF & Trust Commands
    elif cmd == "/oracle":
        if len(parts) < 2:
            console.print("[bold red]❌ Usage: /oracle <your query>[/]")
            return True
        query = " ".join(parts[1:])
        # Direct bypass to Oracle
        cli_module.execute_crew_workflow("ORACLE", query)
        return True
    elif cmd in ["/teach", "/feedback"]:
        cli_module.execute_teach_feedback()
        return True
    elif cmd == "/hrf":
        active_model = get_active_model_name()
        thresh = hrf_manager.get_threshold(active_model)
        base = hrf_manager.get_baseline(active_model)
        
        md_content = f"""
## Hallucination Risk Factor (HRF) Status

* **Active Model:** `{active_model}`
* **Current Threshold:** `{thresh:.2f}`
* **Baseline:** `{base:.2f}`

If a prompt's risk score exceeds this threshold, the query defaults to the Oracle.

### Trust Commands
* `/trust`: Raise the threshold.
* `/doubt`: Lower the threshold.
* `/bs`: Penalize heavily.
* `/risk <prompt>`: Preview the risk score of a specific prompt.
"""
        from rich.panel import Panel
        from rich.markdown import Markdown
        console.print(Markdown(md_content.strip()))
        return True
    elif cmd == "/risk":
        if len(parts) < 2:
            console.print("[bold red]❌ Usage: /risk <your prompt>[/]")
            return True
        query = " ".join(parts[1:])
        from nulka_cli.cli import calculate_hallucination_risk
        score = calculate_hallucination_risk(query)
        active_model = get_active_model_name()
        thresh = hrf_manager.get_threshold(active_model)
        
        status = "[bold green]SAFE[/]" if score < thresh else "[bold red]HIGH RISK (WILL ROUTE TO ORACLE)[/]"
        console.print("\n[bold cyan]Prompt Risk Analysis:[/bold cyan]")
        console.print(f"Query: '{escape(query)}'")
        console.print(f"Score: [bold yellow]{score}[/bold yellow] (Threshold: {thresh:.2f}) -> {status}\n")
        return True
    elif cmd == "/trust":
        active_model = get_active_model_name()
        new_thresh = hrf_manager.trust(active_model)
        console.print(f"[bold green]✅ Trust Increased for {active_model}. HRF threshold is now {new_thresh:.2f}[/]")
        return True
    elif cmd == "/doubt":
        active_model = get_active_model_name()
        new_thresh = hrf_manager.doubt(active_model)
        console.print(f"[bold yellow]⚠️ Trust Decreased for {active_model}. HRF threshold is now {new_thresh:.2f}[/]")
        return True
    elif cmd == "/bs":
        weight = 3.0
        if len(parts) > 1:
            try: weight = float(parts[1])
            except ValueError: pass
        active_model = get_active_model_name()
        new_thresh = hrf_manager.bs(active_model, weight)
        console.print(f"[bold red]🚨 Bullshit Penalty Applied (-{weight}) to {active_model}![/bold red]")
        console.print(f"HRF threshold plummeted to {new_thresh:.2f}")
        if new_thresh <= 1.0:
            console.print("\n[bold red]⚠️ ZERO TRUST MODE INITIATED ⚠️[/bold red]")
            console.print("The local model has lost all trust. All future queries will be locked down and routed to the External Oracle.")
            console.print("Type [bold cyan]/forgive[/bold cyan] to reset trust back to baseline.")
        return True
    elif cmd in ["/forgive", "/reset"]:
        active_model = get_active_model_name()
        new_thresh = hrf_manager.reset(active_model)
        console.print(f"[bold green]🕊️ Trust Forgiven. The local model {active_model} has been granted a clean slate.[/bold green]")
        return True

    elif cmd == "/compress":
        if len(state.history) < 2:
            console.print("[bold yellow]⚠️ Session history is already small. Nothing to compress.[/bold yellow]")
            return True

        console.print("[bold cyan]🔄 Compressing session history using local LLM...[/bold cyan]")
        summary = state.compress_history()
        if summary:
            if "Error" in summary:
                console.print(f"❌ {summary}", style="bold red")
            else:
                console.print("[bold green]✅ Session history successfully compressed into a dense memory block![/bold green]")
                console.print(f"[dim]{summary}[/dim]")
        return True

    elif cmd == "/rewind":
        if state.history:
            state.history.pop()
            state.save_session()
            console.print("[bold green]⏪ Rewound the last conversational turn from memory.[/bold green]")
        else:
            console.print("[bold yellow]⚠️ No history to rewind.[/bold yellow]")
            
        import re
        import time
        
        current_time = time.time()
        recent_baks = []
        for root, _, files in os.walk(os.getcwd()):
            for file in files:
                if file.endswith(".bak"):
                    full_path = os.path.join(root, file)
                    if current_time - os.path.getmtime(full_path) < 3600:
                        recent_baks.append(full_path)
                        
        if recent_baks:
            console.print("\n[bold cyan]Found recently modified files that can be restored:[/bold cyan]")
            for b in recent_baks:
                console.print(f"  📄 [dim]{b}[/dim]")
            
            from nulka_cli.core.state import ask_user_safe
            if ask_user_safe("Restore these files to their original state and delete backups? [y/N] ❯ ").strip().lower() == 'y':
                import shutil
                for b in recent_baks:
                    orig_path = re.sub(r'\.\d{8}_\d{6}\.bak$', '', b)
                    if orig_path != b:
                        shutil.copy2(b, orig_path)
                        os.remove(b)
                        console.print(f"[bold green]✅ Restored:[/] {orig_path}")
        return True

    elif cmd == "/plan":
        if len(parts) < 2:
            console.print("[bold red]❌ Usage: /plan <your goal>[/bold red]")
            return True
            
        goal = " ".join(parts[1:])
        console.print(f"[bold cyan]📝 Engaging Safe Mode Planning for:[/] {goal}")
        console.print("[dim]The Architect will draft a plan.md file without executing any code modifications.[/dim]")
        
        plan_prompt = f"Goal: {goal}\n\nCRITICAL INSTRUCTION: You are in SAFE MODE. You must only research the codebase and strictly use your write_file tool to output a detailed step-by-step checklist to 'plan.md'. Do NOT execute or modify any other files. Do not write actual code yet."
        cli_module.execute_crew_workflow("STRATEGIST", plan_prompt)
        return True

    elif cmd == "/memory":
        md_content = "## 🧠 Current Session Memory\n\n"
        if not state.history:
            md_content += "*Session history is currently empty.*\n\n---\n\n"
        else:
            for i, h in enumerate(state.history):
                preview = h.get('output', '')[:150].replace('\n', ' ')
                md_content += f"**{i+1}. User:** {h.get('prompt')}\n\n> *Agent ({h.get('route')}):* {preview}...\n\n---\n\n"

        rules_path = os.path.expanduser("~/.nulka_cli_rules.md")
        if os.path.exists(rules_path):
            md_content += f"## 🌍 Global Taught Rules ({rules_path})\n\n"
            with open(rules_path, "r", encoding="utf-8") as f:
                content = f.read()
                if content.strip():
                    md_content += content + "\n\n---\n\n"
                else:
                    md_content += "*No global rules have been taught yet (use `/teach`).*\n\n---\n\n"
        
        from rich.markdown import Markdown
        console.print(Markdown(md_content.strip()))
        return True

    elif cmd == "/mcp":
        mcp_config = os.path.expanduser("~/.nulka_cli_mcp.json")
        import json
        
        if not os.path.exists(mcp_config):
            with open(mcp_config, 'w', encoding="utf-8") as f:
                json.dump({"servers": {}}, f)
                
        with open(mcp_config, 'r', encoding="utf-8") as f:
            data = json.load(f)
            
        if len(parts) == 1 or parts[1] == "list":
            console.print("\n[bold cyan]🔌 Configured MCP Servers:[/bold cyan]")
            servers = data.get("servers", {})
            if not servers:
                console.print("[dim]No MCP servers configured. Add one with '/mcp add <name> <cmd>'[/dim]")
            else:
                for name, cmd_str in servers.items():
                    console.print(f"  [bold yellow]{name}[/]: [dim]{cmd_str}[/dim]")
        elif parts[1] == "add" and len(parts) >= 4:
            name = parts[2]
            cmd_str = " ".join(parts[3:])
            data.setdefault("servers", {})[name] = cmd_str
            with open(mcp_config, 'w', encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            console.print(f"[bold green]✅ Added MCP server '{name}'[/bold green]")
        elif parts[1] == "remove" and len(parts) >= 3:
            name = parts[2]
            if name in data.get("servers", {}):
                del data["servers"][name]
                with open(mcp_config, 'w', encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                console.print(f"[bold green]🗑️ Removed MCP server '{name}'[/bold green]")
            else:
                console.print(f"[bold red]❌ MCP server '{name}' not found.[/bold red]")
        else:
            console.print("[bold red]❌ Usage: /mcp [list | add <name> <cmd> | remove <name>][/bold red]")
        return True

    # 8. Unimplemented/Mocked External Extensions
    elif cmd in ["/extensions", "/skills", "/policies", "/hooks", "/shells", "/bashes", "/setup-github", "/resume", "/chat", "/restore", "/settings", "/theme", "/terminal-setup", "/permissions", "/stats", "/bug", "/upgrade", "/privacy"]:
        console.print(f"[yellow]⚠️  Command '{cmd}' is a recognized Gemini command, but is currently stubbed/unsupported in NulkaCLI.[/yellow]")
        console.print("[dim]NulkaCLI focuses on autonomous CrewAI agentic behaviors over direct manual REPL scaffolding.[/dim]")
        return True

    else:
        console.print(f"[bold red]❌ Unknown command: {cmd}. Type /help to list commands.[/]")
        return False


def print_help(console):
    from rich.panel import Panel
    console.print(Panel(
        "[bold yellow]Keybindings & Shortcuts[/bold yellow]\n"
        "  [bold cyan]Enter[/]                  Submit prompt / execute query\n"
        "  [bold cyan]Alt+Enter / Esc+Enter[/]  Insert literal newline (multi-line input)\n"
        "  [bold cyan]Ctrl+J[/]                 Insert literal newline (alternative)\n"
        "  [bold cyan]Ctrl+C[/]                 Interrupt & stop running model generation\n"
        "  [bold cyan]Ctrl+D[/]                 Exit NulkaCLI session (when prompt is empty)\n\n"
        "[bold yellow]Core System[/bold yellow]\n"
        "  [bold cyan]/about[/]              Show NulkaCLI version and diagnostic info\n"
        "  [bold cyan]/clear[/]              Clear the screen and reset session context\n"
        "  [bold cyan]/rewind[/]             Undo the last turn and restore modified files\n"
        "  [bold cyan]/vim[/]                Toggle Vim-mode keybindings for the prompt\n"
        "  [bold cyan]/tui[/]                Launch modern, non-blocking Textual TUI interface\n"
        "  [bold cyan]/quit[/]               Exit session (use --delete to purge history)\n\n"
        "[bold yellow]Workflow & Planning[/bold yellow]\n"
        "  [bold cyan]/plan <goal>[/]        Safe Mode: Architect writes plan.md without executing\n"
        "  [bold cyan]/mcp [cmd][/]           Manage Model Context Protocol servers (add, list, remove)\n\n"
        "[bold yellow]Tools, Output, & Agents[/bold yellow]\n"
        "  [bold cyan]/expand[/]             View the last truncated output in a full-screen pager\n"
        "  [bold cyan]/compress[/]           Compress session history to a single dense memory block\n"
        "  [bold cyan]/memory[/]             View the current compressed session memory and rules\n"
        "  [bold cyan]/copy[/]               Copy the last raw output to your clipboard\n"
        "  [bold cyan]/copy_log[/]           Copy full action and thought stream logs to clipboard\n"
        "  [bold cyan]/tools[/]              List available capabilities\n"
        "  [bold cyan]/agents[/]             List available specialized AI departments\n"
        "  [bold cyan]/oracle <query>[/]     Directly query the External Universal Oracle\n"
        "  [bold cyan]/metrics[/]            Toggle the live bottom toolbar for performance metrics\n"
        "  [bold cyan]/debug[/]              Toggle verbose agent thoughts & details\n\n"
        "[bold yellow]Workspace & Directory Management[/bold yellow]\n"
        "  [bold cyan]/init[/]               Initialize a new workspace in the current directory\n"
        "  [bold cyan]/cd [path][/]          Change current working directory\n"
        "  [bold cyan]/pwd[/]                Show current working directory path\n"
        "  [bold cyan]/ls [path][/]           List contents of a directory (defaults to current)\n"
        "  [bold cyan]/workspace [cmd][/]    Manage active directories (subcmds: show, add, set)\n\n"
        "[bold yellow]Learning & Trust (HRF)[/bold yellow]\n"
        "  [bold cyan]/teach[/]              Flag the last response as incomplete & teach the agent\n"
        "  [bold cyan]/hrf[/]                Show current Hallucination Risk Factor settings\n"
        "  [bold cyan]/risk <prompt>[/]      Preview the hallucination risk score of a prompt\n"
        "  [bold cyan]/trust[/]              Trust model more (raises Oracle threshold)\n"
        "  [bold cyan]/doubt[/]              Trust model less (lowers Oracle threshold)\n"
        "  [bold cyan]/bs [weight][/]        Apply hallucination penalty to drop trust\n"
        "  [bold cyan]/forgive[/]            Reset trust back to clean-slate baseline\n\n"
        "[bold yellow]Model Management[/bold yellow]\n"
        "  [bold cyan]/models[/]             Show downloaded & loaded Ollama models\n"
        "  [bold cyan]/pull <name>[/]        Download a new model from the Ollama library\n"
        "  [bold cyan]/load <name>[/]        Load a model into memory\n"
        "  [bold cyan]/stop <name>[/]        Stop a running model\n"
        "  [bold cyan]/rm <name>[/]          Remove a model from the system",
        title="NulkaCLI Command Reference", border_style="blue"
    ))
