import ast

# --- MONKEY-PATCH AST FOR PYTHON 3.14+ ---
# docstring-parser 0.15 (pinned by crewai 0.11.2) uses ast.NameConstant, 
# which was deprecated in 3.8 and removed in 3.14. 
if not hasattr(ast, 'NameConstant'):
    # In modern AST, NameConstant(value) is just Constant(value)
    ast.NameConstant = ast.Constant

import os
import sys
import glob
import subprocess
from datetime import datetime
from dotenv import load_dotenv
import warnings
import logging

# Suppress Pydantic warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

# Suppress OpenTelemetry TracerProvider overriding warnings caused by sequential crew kickoffs
logging.getLogger("opentelemetry.trace").setLevel(logging.ERROR)
logging.getLogger("opentelemetry.sdk.trace").setLevel(logging.ERROR)

CONFIG_PATH = os.path.expanduser("~/.nulka_cli_env")
# Load environment variables on startup
load_dotenv(CONFIG_PATH)

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from crewai import Crew, Task, Process

# Patch CrewAI telemetry to prevent HTTP connection errors on execution
for module_name in ('crewai.telemtry.telemetry', 'crewai.telemetry.telemetry'):
    try:
        import importlib
        telemetry_module = importlib.import_module(module_name)
        def _patched_telemetry_init(self):
            self.ready = False
        telemetry_module.Telemetry.__init__ = _patched_telemetry_init
    except (ImportError, AttributeError):
        pass

from langchain.tools import tool
from nulka_cli.utils import (
    instantiate_agents, 
    get_system_context, 
    ollama_llm,
    is_ollama_running,
    start_ollama_server,
    get_local_models,
    get_loaded_models
)

# Initialize Rich Console
console = Console()

# Initialize Agents
agents = instantiate_agents()

# Global Debug Mode to control agent thought verbosity
DEBUG_MODE = False

from nulka_cli.core.state import state

def format_condensed_output(text: str, max_lines: int = 40) -> str:
    """Smartly truncates massive string outputs for the terminal UI."""
    if not text:
        return text
    lines = text.split("\n")
    if len(lines) <= max_lines:
        return text
        
    first_part = "\n".join(lines[:15])
    last_part = "\n".join(lines[-15:])
    hidden = len(lines) - 30
    
    divider = f"\n\n[dim cyan]... [ {hidden} Lines Condensed. Type /expand to view full output ] ...[/dim cyan]\n\n"
    return first_part + divider + last_part

def analyze_prompt_intent(prompt: str) -> dict:
    """
    Uses the General Assistant LLM to evaluate the prompt for BOTH missing context (scrutiny) 
    and task categorization (routing) in a single, intelligent step.
    """
    history_context = ""
    if state.history:
        recent = state.history[-2:]
        history_context = "\n--- Recent Conversation History ---\n"
        for h in recent:
            out = h.get('output', '')
            out_preview = out[:300] + "... [TRUNCATED]" if len(out) > 300 else out
            history_context += f"User: {h.get('prompt')}\nAgent: {out_preview}\n"
        history_context += "-----------------------------------\n\n"

    system_prompt = (
        "You are the NulkaCLI Lead Coordinator.\n"
        "Your job is to read the user's prompt (and history) and perform two tasks:\n\n"
        "TASK 1 - SCRUTINY:\n"
        "Determine if the prompt is missing critical context (e.g., they ask to edit a file but don't name the file). "
        "If it is impossible to proceed, write a clarification question. If you CAN proceed (or if it's a general question), output 'PROCEED'. "
        "IMPORTANT: If the user says something conversational like 'let go again', 'lets pick up where we left off', or 'continue', you MUST output 'PROCEED' because the General Assistant knows how to handle these automatically based on its learned rules.\n\n"
        "TASK 2 - ROUTING:\n"
        "Assign the request to EXACTLY ONE of these versatile archetypes based on the intent:\n"
        "- STRATEGIST: Planning, structural design, architecture, defining roadmaps, or breaking down tasks.\n"
        "- CREATOR: Writing code, generating documents, writing essays, creating configuration files, or building features.\n"
        "- AUDITOR: Reviewing work, QA testing, searching for secrets/vulnerabilities, verifying compliance, or factual fact-checking.\n"
        "- ANALYST: Researching topics, parsing data/logs, running system operations/shell diagnostics, or extracting intelligence.\n"
        "- GENERAL: General conversational chats or vague instructions (e.g. 'let's go', 'continue').\n\n"
        "OUTPUT FORMAT (You must output exactly these two lines):\n"
        "SCRUTINY: [Your question or PROCEED]\n"
        "ROUTE: [Category Name]\n\n"
        f"{history_context}"
        f"Prompt: {prompt}"
    )
    
    result = {
        "scrutiny": "PROCEED",
        "route": "GENERAL"
    }
    
    try:
        response = ollama_llm.invoke(system_prompt).strip()
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            if line.upper().startswith("SCRUTINY:"):
                val = line[len("SCRUTINY:"):].strip()
                result["scrutiny"] = val if val else "PROCEED"
            elif line.upper().startswith("ROUTE:"):
                val = line[len("ROUTE:"):].strip().upper()
                for cat in ["STRATEGIST", "CREATOR", "AUDITOR", "ANALYST", "GENERAL", "ORACLE"]:
                    if cat in val:
                        result["route"] = cat
                        break
        return result
    except Exception as e:
        console.print(f"[bold red]Router Error during analysis: {e}[/]")
        return result

def calculate_hallucination_risk(prompt: str) -> int:
    """Evaluates the prompt against common local LLM hallucination pitfalls."""
    import re
    p = prompt.lower()
    score = 0
    
    # 1. External URLs (Models heavily hallucinate reading/browsing live web)
    if re.search(r'(http[s]?://|www\.)', p):
        score += 8
        
    # 2. Spatial/Location Data (Lack of physical grounding)
    if re.search(r'\b(near me|closest|nearest|directions to|where is the)\b', p):
        score += 8
        
    # 3. Temporal/Live Data (Models don't know current dates, live news, or stock prices)
    if re.search(r'\b(latest|today|current version|release|weather|stock|news|live)\b', p):
        score += 6
        
    # 4. Obscure Facts / Dynamic Entities
    if re.search(r'\b(who won|population of|president of|ceo of)\b', p):
        score += 5
        
    # 5. Arithmetic / Strict Logic 
    if re.search(r'\b(calculate|multiply|divide|square root)\b', p):
        score += 4
        
    return min(score, 10)

from nulka_cli.hrf_manager import hrf_manager

def get_active_model_name() -> str:
    """Helper to fetch the primary loaded model."""
    from nulka_cli.utils import get_best_available_model
    return get_best_available_model()

def route_request(prompt: str, predefined_route: str = None) -> str:
    """Integrates dynamic HRF evaluation and routes the request."""

    # 0. Evaluate Hallucination Risk Factor (HRF)
    hrf_score = calculate_hallucination_risk(prompt)
    active_model = get_active_model_name()
    dynamic_threshold = hrf_manager.get_threshold(active_model)

    # ZERO TRUST MITIGATION LOGIC
    if dynamic_threshold <= 1.0:
        console.print("\n[bold red]⚠️  ZERO TRUST LOCKDOWN ACTIVE  ⚠️[/bold red]")
        console.print(f"[yellow]The local model '{active_model}' has completely lost your trust.[/yellow]")
        console.print("[dim]Routing 100% of prompts to the External Oracle.[/dim]")

        # Check for model swap possibility
        available_models = [m for m in get_local_models() if m != active_model]
        if available_models:
            console.print("\n[bold cyan]💡 Mitigation Available: Switch to a different Local Model?[/bold cyan]")
            from nulka_cli.core.state import ask_user_safe
            choice = ask_user_safe("Select option ❯ ", style_dict={'prompt': 'ansicyan bold'}).lower()
            if choice and choice != 's':
                try:
                    idx = int(choice)
                    if 0 <= idx < len(available_models):
                        new_model = available_models[idx]
                        import os
                        from dotenv import set_key
                        CONFIG_PATH = os.path.expanduser("~/.nulka_cli_env")
                        set_key(CONFIG_PATH, "LOCAL_MODEL", new_model)
                        console.print(f"[bold green]✅ Success! Active model swapped to {new_model}.[/bold green]")
                        console.print("[yellow]Please restart NulkaCLI for the core swap to take effect![/yellow]")
                        return "SWAP_RESTART"
                except ValueError:
                    pass

            return "ORACLE"

    if hrf_score >= dynamic_threshold:
        console.print(f"[bold yellow]⚠️ High Hallucination Risk Factor Detected ({hrf_score} >= threshold {dynamic_threshold:.1f}). Defaulting to Universal Oracle...[/]")
        return "ORACLE"
        
    return predefined_route if predefined_route else "GENERAL"

def execute_crew_workflow(route: str, prompt: str):
    """Dynamically assembles and kicks off the perfect Crew of agents based on the route."""
    context = get_system_context()
    
    # Inject conversational history into the prompt for the agents
    history_context = ""
    if state.history:
        recent = state.history[-1] # Just the last turn to keep context tight
        out_preview = recent.get('output', '')[:200] + "..."
        # Provide the absolute path to the active cache file
        import os
        cache_path = os.path.join(state.get_workspace_dir(), "last_output_cache.txt")
        if os.path.exists(cache_path):
            history_context = (
                f"\n--- CACHED CONTEXT FROM PREVIOUS TURN ---\n"
                f"User previously asked: {recent.get('prompt')}\n"
                f"Agent preview: {out_preview}\n"
                f"CRITICAL RULES FOR CONTINUATION:\n"
                f"1. The full, complete result of your previous turn is safely cached in the file: '{cache_path}'\n"
                f"2. Only use the 'read_file' tool to read '{cache_path}' if the user's current request explicitly asks to modify or summarize your PREVIOUS response.\n"
                f"3. If the user asks to read, use, or analyze actual workspace files (e.g., Markdown files, Python files), read those actual files directly using their respective paths. Do NOT read '{cache_path}' in those cases.\n"
                f"-----------------------------------------\n\n"
            )
        
    full_prompt_with_history = f"{history_context}Current Request: '{prompt}'"
    
    inputs = {
        "user_prompt": prompt,
        "current_time": context["current_time"],
        "system_os": context["system_os"],
        "system_platform": context["system_platform"],
        "geolocation": context["geolocation"],
        "working_directory": context.get("working_directory", os.getcwd())
    }

    # Map routes to Agent combinations & Tasks
    if route == "ORACLE":
        tasks = [
            Task(
                description=(
                    f"The user asked a high-risk query: {full_prompt_with_history}\n"
                    f"1. You MUST use the 'oracle_cli_tool' exactly once to execute this exact query: '{prompt}'.\n"
                    f"2. You MUST NOT modify or summarize the response.\n"
                    f"3. Return the EXACT string returned by the oracle_cli_tool as your final answer."
                ),
                expected_output="The exact, unmodified string returned by the oracle tool.",
                agent=agents["external_oracle"]
            )
        ]
        crew_agents = [agents["external_oracle"]]
        status_msg = "Consulting Oracle..."
        
    elif route == "STRATEGIST":
        tasks = [
            Task(
                description=f"Analyze the requirement: {full_prompt_with_history}. Design a high-level roadmap, architecture, or blueprint based on the user's need.",
                expected_output="A clean, comprehensive Markdown-formatted plan with actionable steps or architectural designs.",
                agent=agents["strategist"]
            )
        ]
        crew_agents = [agents["strategist"]]
        status_msg = "The Strategist is drawing up blueprints..."

    elif route == "CREATOR":
        tasks = [
            Task(
                description=f"Implement the requirement: {full_prompt_with_history}. Read relevant context files and write code, draft documents, or generate configuration.",
                expected_output="Directly modified workspace files or a complete drafted output.",
                agent=agents["creator"]
            )
        ]
        crew_agents = [agents["creator"]]
        status_msg = "The Creator is implementing your request..."

    elif route == "AUDITOR":
        tasks = [
            Task(
                description=f"Review the target scope: {full_prompt_with_history}. Write/run tests, search for vulnerabilities/secrets, or verify factual compliance.",
                expected_output="An audit report, test execution summary, or security patch.",
                agent=agents["auditor"]
            )
        ]
        crew_agents = [agents["auditor"]]
        status_msg = "The Auditor is verifying functionality and security..."

    elif route == "ANALYST":
        tasks = [
            Task(
                description=f"Investigate the scope: {full_prompt_with_history}. Parse logs, research datasets, execute diagnostic shell commands, or extract intelligence.",
                expected_output="A synthesized research summary or diagnostic report with citations.",
                agent=agents["analyst"]
            )
        ]
        crew_agents = [agents["analyst"]]
        status_msg = "The Analyst is running deep diagnostics and research..."

    else: # GENERAL
        # General Assistant route
        tasks = [
            Task(
                description=f"Respond helpfully, clearly, and contextualized to: {full_prompt_with_history}. Feel free to consult workspace files or search the web to make your answer highly precise.",
                expected_output="A helpful, professional response addressing the query fully.",
                agent=agents["assistant"]
            )
        ]
        crew_agents = [agents["assistant"]]
        status_msg = "General Assistant is gathering information..."

    # === ADVANCED HALLUCINATION MITIGATIONS ===
    hrf_score = calculate_hallucination_risk(prompt)
    
    # 1. Dynamic Temperature Scaling
    if hrf_score <= 3:
        temp = 0.7
    elif hrf_score <= 6:
        temp = 0.3
    else:
        temp = 0.0
        
    from nulka_cli.utils import ollama_llm
    if hasattr(ollama_llm, 'temperature'):
        ollama_llm.temperature = temp
    if DEBUG_MODE:
        console.print(f"[dim]🌡️  Dynamic Temperature Scaling: HRF={hrf_score} ➔ LLM Temperature set to {temp}[/dim]")

    # 2. Multi-Agent Cross-Examination (Fact Checker)
    # If the HRF score is medium-high (4 to 7) and we aren't already bypassing to Oracle
    if 4 <= hrf_score <= 7 and route != "ORACLE":
        if "fact_checker" in agents:
            fact_check_task = Task(
                description=(
                    f"Review the drafted response generated by the previous agent for the user's request: '{prompt}'.\n"
                    f"Critically analyze it for factual inaccuracies, hallucinations, or ungrounded claims.\n"
                    f"If you detect hallucinations, you MUST rewrite the output to be strictly factual, stripping out any guessed information."
                ),
                expected_output="A peer-reviewed, factually grounded final response to the user.",
                agent=agents["fact_checker"]
            )
            tasks.append(fact_check_task)
            crew_agents.append(agents["fact_checker"])
            if DEBUG_MODE:
                console.print(f"[dim]🛡️  Multi-Agent Peer Review: Fact-Checker appended to workflow due to HRF Score {hrf_score}[/dim]")

    # Update state tracking for the /teach feedback loop
    state.last_user_prompt = prompt
    state.last_route = route

    # Apply debug/verbosity settings dynamically to all agents in the current crew
    for agent in crew_agents:
        agent.verbose = DEBUG_MODE

    # Execute dynamic Crew
    import time
    start_time = time.time()
    
    console.print(f"\n[bold green]🚀 {status_msg}[/]\n")
    crew = Crew(
        agents=crew_agents,
        tasks=tasks,
        process=Process.sequential,
        verbose=DEBUG_MODE
    )
    crew_output = crew.kickoff()
    result_text = str(crew_output)
        
    end_time = time.time()
    state.last_execution_time = end_time - start_time

    # Determine header message and Panel title dynamically
    if route == "GENERAL":
        completion_msg = "✨ Answer Completed!"
        title_str = "Answer"
    else:
        completion_msg = "✅ Task Execution Completed!"
        title_str = "Response & Deliverables"

    # Save interaction state persistently
    state.append_interaction(prompt, route, result_text)

    # Construct the Breadcrumb Path of executed steps
    steps = ["Router"]
    if route == "ORACLE":
        steps.extend(["Universal Oracle (HRF Bypass)"])
    elif route == "STRATEGIST":
        steps.extend(["The Strategist"])
    elif route == "CREATOR":
        steps.extend(["The Creator"])
    elif route == "AUDITOR":
        steps.extend(["The Auditor"])
    elif route == "ANALYST":
        steps.extend(["The Analyst"])
    else: # GENERAL
        steps.extend(["General Assistant"])

    if 4 <= hrf_score <= 7 and route != "ORACLE":
        steps.append("Fact-Checker (Peer Review)")

    # Dynamically check if the Oracle CLI Tool was invoked during this run
    if "Oracle Answer Retrieved" in result_text or "Oracle CLI" in result_text or "retrieved from the Oracle" in result_text:
        if route != "ORACLE": # Prevent duplicating the step if already added
            steps.append("External Oracle Fallback")

    # Render breadcrumb trail cleanly
    breadcrumb_trail = " ➔ ".join([f"[bold cyan]{step}[/]" for step in steps])

    console.print(f"\n[bold green]{completion_msg}[/]")
    console.print(f"{breadcrumb_trail}\n")
    
    # Save absolute raw output to state for the /expand command
    state.last_full_output = result_text
    
    # Condense string for UI display
    condensed_result = format_condensed_output(result_text)
    console.print(Panel(condensed_result, title=f"[bold white]{title_str}[/]", border_style="green"))
    
    # Stabilize HRF baseline for the active model after a successful completion
    active_model = get_active_model_name()
    new_thresh = hrf_manager.stabilize(active_model)
    # console.print(f"[dim]HRF stabilized to {new_thresh:.2f}[/dim]") # Hidden debug

def execute_teach_feedback():
    """Triggers the learning loop on the last executed query robustly by manually invoking tools."""
    if not state.last_user_prompt or not state.last_route:
        console.print("[bold red]❌ No previous query found to teach from. Please submit a query first.[/]")
        return

    console.print(f"\n[bold yellow]🎓 [Onboarding Feedback Loop] Activating Teacher...[/bold yellow]")
    console.print(f"Teaching from query: [bold cyan]'{state.last_user_prompt}'[/bold cyan] (Route: [bold magenta]{state.last_route}[/bold magenta])")

    # Map the LAST_ROUTE to the correct agent filename/key to update
    route_to_agent_map = {
        "STRATEGIST": "strategist",
        "CREATOR": "creator",
        "AUDITOR": "auditor",
        "ANALYST": "analyst",
        "GENERAL": "assistant",
        "ORACLE": "assistant"
    }
    target_agent_key = route_to_agent_map.get(state.last_route, "assistant")

    console.print("[bold yellow]🚀 Consulting Oracle...[/]")
    from nulka_cli.tools.oracle_cli_tool import OracleCLITool
    from nulka_cli.tools.interactive_teacher_tool import InteractiveTeacherTool
    
    # 1. Fetch Oracle Truth manually
    oracle_tool = OracleCLITool()
    oracle_prompt = (
        f"A local AI agent failed to properly process the following user request:\n"
        f"'{state.last_user_prompt}'\n\n"
        f"Please provide the correct solution. More importantly, format your response as an omnipotent, "
        f"universal 'Lesson Learned' that is NOT specific to this current project or its files. "
        f"Abstract away project details and provide a generalized rule that the agent should follow for all future requests of this nature."
    )
    oracle_answer = oracle_tool._run(oracle_prompt)
    
    console.print(f"\n[bold green]✨ Oracle Answer Retrieved:[/]\n{oracle_answer}\n")
    
    # Check if Oracle failed (e.g., timeout, connection error, cmd not found, etc.)
    oracle_failed = (
        oracle_answer.startswith("Error:") or 
        oracle_answer.startswith("An unexpected error occurred") or
        "returned error code" in oracle_answer or
        "timed out" in oracle_answer.lower()
    )

    if oracle_failed:
        console.print(f"\n[bold red]⚠️  The External Oracle query failed or timed out: [/bold red]")
        console.print(f"[yellow]{oracle_answer}[/yellow]\n")
        console.print("[bold yellow]Because the Oracle is unavailable, we cannot auto-formulate a lesson from it.[/bold yellow]")
        console.print("However, you can still formulate your own manual 'Lesson Learned' rule below. Ensure it is abstract and NOT specific to this project, or leave it blank to cancel.")
        
        from nulka_cli.core.state import ask_user_safe
        custom_rule = ask_user_safe(
            "\nEnter your universal 'Lesson Learned' rule (or press Enter to cancel) ❯ ",
            style_dict={'prompt': 'ansiyellow bold'}
        )

        if not custom_rule:
            console.print("[bold yellow]Teaching session cancelled. No rule added.[/bold yellow]")
            return

        proposed_rules = f"When faced with requests similar to '{state.last_user_prompt}', apply the following universal guideline:\n{custom_rule}\nAlways ensure this rule is applied abstractly to the current context."
    else:
        # 2. Invoke Interactive Tool manually
        proposed_rules = f"When faced with requests similar to '{state.last_user_prompt}', apply the following universal guideline:\n{oracle_answer}\nAlways ensure this rule is applied abstractly to the current context."
    
    teacher_tool = InteractiveTeacherTool()
    result = teacher_tool._run(agent_name=target_agent_key, proposed_rules=proposed_rules)

    # Automatically lower trust (doubt) because the local model failed
    active_model = get_active_model_name()
    new_thresh = hrf_manager.doubt(active_model)

    console.print("\n[bold green]✨ Feedback Learning Session Completed![/]")
    console.print(f"[dim]Note: Local model trust decreased. HRF threshold is now {new_thresh:.2f}[/dim]")
    console.print(Panel(result, title="[bold white]Feedback Output[/]", border_style="yellow"))

def execute_expand_pager():
    """Opens the LAST_FULL_OUTPUT in a native full-screen terminal pager."""
    if not state.last_full_output:
        console.print("[bold red]❌ No previous output to expand. Please run a query first.[/]")
        return
        
    with console.pager():
        console.print(state.last_full_output)

def show_ollama_models():
    """Renders a beautiful table of installed and loaded models."""
    if not is_ollama_running():
        console.print("[bold red]❌ Ollama is not running.[/]")
        return
        
    with console.status("[bold yellow]📥 Fetching model statuses from Ollama daemon...[/]"):
        local = get_local_models()
        loaded = get_loaded_models()
        
    table = Table(title="🦙 Ollama Local Model Hub", header_style="bold magenta", border_style="cyan")
    table.add_column("Model Name", style="bold white")
    table.add_column("Status", justify="center")
    
    if not local:
        table.add_row("[italic yellow]No models found[/]", "")
    else:
        for model in local:
            # Match model name cleanly (e.g. qwen2.5-coder:latest vs qwen2.5-coder)
            is_active = any(model in l or l in model for l in loaded)
            status_text = "[bold green]ACTIVE (Loaded)[/]" if is_active else "[dim]IDLE (Cached)[/]"
            table.add_row(model, status_text)
            
    console.print(table)

def pull_ollama_model(model_name: str):
    """Pulls a new model via Ollama native progress indicator."""
    if not is_ollama_running():
        console.print("[bold red]❌ Ollama is not running. Please start the server first.[/]")
        return
        
    console.print(f"[bold yellow]📥 Pulling model '{model_name}' natively from Ollama Library...[/]")
    try:
        # Run natively so the user can see Ollama's dynamic progress bars
        subprocess.run(["ollama", "pull", model_name], check=True)
        console.print(f"\n[bold green]✅ Model '{model_name}' pulled successfully![/]")
    except subprocess.CalledProcessError:
        console.print(f"\n[bold red]❌ Failed to pull model '{model_name}'. Please verify the name is correct.[/]")
    except Exception as e:
        console.print(f"\n[bold red]❌ Error: {e}[/]")

def load_ollama_model(model_name: str):
    """Loads (runs) a model via Ollama."""
    if not is_ollama_running():
        console.print("[bold red]❌ Ollama is not running. Please start the server first.[/]")
        return
        
    console.print(f"[bold yellow]⏳ Loading model '{model_name}' natively via Ollama...[/]")
    try:
        # Running the model natively in an interactive process is complicated as it drops into an interactive shell.
        # But 'ollama run' will load the model into memory.
        # Alternatively we can use API to preload. 
        # Using subprocess but not attaching to interactive shell. 
        # But wait, it will drop to shell if we just 'ollama run'.
        # Best is to query the API to load it empty, or use a trick.
        # We can just update the LOCAL_MODEL in the env file and ask user to restart.
        
        # But wait, we want to just load it into memory maybe?
        # A simple 'ollama run' with an empty prompt loads it and exits.
        subprocess.run(["ollama", "run", model_name, ""], check=True, capture_output=True)
        console.print(f"\n[bold green]✅ Model '{model_name}' loaded into memory successfully![/]")
    except subprocess.CalledProcessError as e:
        console.print(f"\n[bold red]❌ Failed to load model '{model_name}'. Please verify the name is correct. {e.stderr}[/]")
    except Exception as e:
        console.print(f"\n[bold red]❌ Error: {e}[/]")

def stop_ollama_model(model_name: str):
    """Stops a running model via Ollama."""
    if not is_ollama_running():
        console.print("[bold red]❌ Ollama is not running.[/]")
        return
        
    console.print(f"[bold yellow]🛑 Stopping model '{model_name}'...[/]")
    try:
        subprocess.run(["ollama", "stop", model_name], check=True)
        console.print(f"\n[bold green]✅ Model '{model_name}' stopped successfully![/]")
    except subprocess.CalledProcessError:
        console.print(f"\n[bold red]❌ Failed to stop model '{model_name}'. Is it currently running?[/]")
    except Exception as e:
        console.print(f"\n[bold red]❌ Error: {e}[/]")

def remove_ollama_model(model_name: str):
    """Removes a model via Ollama."""
    if not is_ollama_running():
        console.print("[bold red]❌ Ollama is not running.[/]")
        return
        
    console.print(f"[bold yellow]🗑️  Removing model '{model_name}'...[/]")
    try:
        subprocess.run(["ollama", "rm", model_name], check=True)
        console.print(f"\n[bold green]✅ Model '{model_name}' removed successfully![/]")
    except subprocess.CalledProcessError:
        console.print(f"\n[bold red]❌ Failed to remove model '{model_name}'. Please verify the name is correct.[/]")
    except Exception as e:
        console.print(f"\n[bold red]❌ Error: {e}[/]")

def run_onboarding_wizard():
    """Starts a beautiful Python-native onboarding setup wizard if no config is found."""
    from prompt_toolkit import prompt
    from prompt_toolkit.styles import Style
    import shutil
    
    console.print("\n")
    banner = (
        "[bold cyan]========================================================================[/bold cyan]\n"
        "                 [bold yellow]🌟 Welcome to NulkaCLI Onboarding! 🌟[/bold yellow]\n"
        "          Let's configure your system-wide Oracle fallback tool.\n"
        "[bold cyan]========================================================================[/bold cyan]\n"
    )
    console.print(Panel(banner, border_style="cyan"))
    
    # Scan for common AI CLI tools
    console.print("[bold blue]🔍 Scanning system path for available AI CLIs...[/bold blue]")
    candidates = ["gemini", "chatgpt", "claude"]
    found_clis = []
    
    for cli in candidates:
        if shutil.which(cli):
            found_clis.append(cli)
            console.print(f"  [bold green]➔ Found:[/] {cli} at [dim]{shutil.which(cli)}[/dim]")
            
    # Interactive selection using prompt_toolkit
    style = Style.from_dict({
        'prompt': 'ansicyan bold',
    })
    
    oracle_cmd = "gemini --prompt" # Default fallback
    
    if found_clis:
        console.print("\n[bold yellow]Choose an AI CLI to act as your external Oracle fallback:[/bold yellow]")
        for i, cli in enumerate(found_clis):
            console.print(f"  [[bold cyan]{i}[/]] {cli}")
        console.print("  [[bold cyan]c[/]] Enter a custom command string")
        
        from nulka_cli.core.state import ask_user_safe
        choice = ask_user_safe("Select option [default: 0] > ", style_dict={'prompt': 'ansicyan bold'}).lower()
        if not choice:
            console.print("\n[bold red]Onboarding cancelled. Falling back to default 'gemini --prompt'.[/bold red]")
            choice = "0"
        
        if choice == 'c':
            custom_cmd = ask_user_safe("Enter your custom CLI command string (e.g. chatgpt -p) > ", style_dict={'prompt': 'ansicyan bold'})
            oracle_cmd = custom_cmd if custom_cmd else "gemini --prompt"
        else:
            try:
                idx = int(choice)
                if idx < len(found_clis):
                    selected = found_clis[idx]
                    oracle_cmd = "gemini --prompt" if selected == "gemini" else selected
                else:
                    oracle_cmd = "gemini --prompt"
            except ValueError:
                oracle_cmd = "gemini --prompt"
    else:
        console.print("\n[bold yellow]No standard AI CLIs were found on your PATH.[/bold yellow]")
        from nulka_cli.core.state import ask_user_safe
        custom_cmd = ask_user_safe("Enter your Oracle CLI command string [default: gemini --prompt] > ", style_dict={'prompt': 'ansicyan bold'})
        oracle_cmd = custom_cmd if custom_cmd else "gemini --prompt"
        
    console.print(f"\n[bold green]✅ Configured Oracle Command:[/] [bold magenta]{oracle_cmd}[/bold magenta]")
    
    # Save to global config file
    try:
        with open(CONFIG_PATH, "w") as f:
            f.write("# NulkaCLI Environment Configuration\n")
            f.write(f'ORACLE_CMD="{oracle_cmd}"\n')
        console.print(f"[bold green]💾 Saved configuration to {CONFIG_PATH} successfully![/bold green]\n")
        
        # Load dotenv to reload environment variables on the fly
        load_dotenv(CONFIG_PATH, override=True)
    except Exception as e:
        console.print(f"[bold red]❌ Failed to save configuration: {e}[/bold red]\n")

def run_interactive_cli():
    import os
    global DEBUG_MODE
    # 0. Onboarding Check
    if not os.path.exists(CONFIG_PATH) and not os.getenv("ORACLE_CMD"):
        run_onboarding_wizard()

    # 1. Startup Ollama Daemon Check & Boot
    import platform
    if not is_ollama_running():
        console.print("[bold yellow]⚠️ [Ollama] Server is not running. Attempting to start...[/]")
        with console.status("[bold green]🚀 [Ollama] Starting background daemon and verifying connection...[/]"):
            success, msg = start_ollama_server()
        if success:
            console.print("[bold green]✅ [Ollama] Daemon started successfully and verified online![/]")
        else:
            console.print(f"[bold red]❌ [Ollama] Could not start server: {msg}[/]")
            console.print("[yellow]Please run 'ollama serve' in another terminal, then restart this CLI.[/]")
            sys.exit(1)

    # Welcome banner
    welcome_text = Text()
    welcome_text.append("\n🤖 NulkaCLI (Enterprise Multi-Agent Workspace)\n", style="bold green")
    welcome_text.append("Operating System: ", style="dim")
    welcome_text.append(f"{platform.system()} {platform.release()}\n", style="bold cyan")
    welcome_text.append("Local Time: ", style="dim")
    welcome_text.append(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n", style="bold yellow")
    welcome_text.append("Active Local Model: ", style="dim")
    welcome_text.append(f"{get_active_model_name()}\n", style="bold magenta")
    welcome_text.append("Available Agents: ", style="dim")
    welcome_text.append("Strategist, Creator, Auditor, Analyst, Router, Teacher, Oracle\n", style="bold magenta")
    welcome_text.append("Special Tooling: ", style="dim")
    welcome_text.append("Workspace Automation, Web Search, Dynamic HRF & Fallback Oracle\n", style="bold blue")
    welcome_text.append("Interactive Help: ", style="dim")
    welcome_text.append("Type /help to view command list or /risk to preview prompt danger\n", style="bold green")
    welcome_text.append("Type '/quit', 'exit', or 'quit' to terminate.\n", style="italic")
    
    console.print(Panel(welcome_text, title="[bold green]NulkaCLI Session[/]", border_style="green"))
    
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.styles import Style
    from prompt_toolkit.key_binding import KeyBindings
    import os
    history_file = os.path.join(os.path.expanduser("~"), ".nulka_cli_history")
    
    from nulka_cli.ui.statusbar import StatusBar
    from nulka_cli.ui.slash_commands import handle_slash_command

    # Define custom KeyBindings for multiline Shift+Enter insertion
    kb = KeyBindings()

    @kb.add('enter')
    def _(event):
        """Enter key validates and submits the prompt instead of inserting newline."""
        event.current_buffer.validate_and_handle()

    @kb.add('c-j')
    def _(event):
        """Ctrl+J (which Unix terminals send on Shift+Enter) inserts a literal newline."""
        event.current_buffer.insert_text('\n')

    @kb.add('escape', 'enter')
    def _(event):
        """Alt+Enter (Escape then Enter) inserts a literal newline in the prompt."""
        event.current_buffer.insert_text('\n')

    session = PromptSession(history=FileHistory(history_file), key_bindings=kb)
    
    import sys
    this_module = sys.modules[__name__]
    
    while True:
        try:
            # We style the bottom toolbar slightly if metrics are on
            style_dict = {}
            if state.show_metrics:
                style_dict['bottom-toolbar'] = 'bg:#222222 #ffffff'
            prompt_style = Style.from_dict(style_dict)
            
            user_input = session.prompt(
                "\n✦ ❯ ", 
                bottom_toolbar=StatusBar.get_toolbar, 
                style=prompt_style,
                vi_mode=state.vim_mode,
                multiline=True
            )
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold yellow]Goodbye human[/]")
            break
            
        user_input = user_input.strip()
        if not user_input:
            continue
            
        if user_input.lower() in ['/quit', 'exit', 'quit']:
            console.print("[bold yellow]Goodbye human[/]")
            break
            
        # Handle slash commands using the new dedicated handler
        if user_input.startswith("/"):
            parts = user_input.split()
            cmd = parts[0].lower()
            handle_slash_command(cmd, parts, console, session, this_module)
            continue

        # 1. Analyze Intent (Scrutiny + Routing in one pass)
        with console.status("[bold yellow]🤔 [Lead Coordinator] Analyzing intent & context...[/]"):
            analysis = analyze_prompt_intent(user_input)
            
        scrutiny_result = analysis.get("scrutiny", "PROCEED")
        proposed_route = analysis.get("route", "GENERAL")
            
        if scrutiny_result != "PROCEED":
            console.print(f"[bold yellow]🤔 [Coordinator Question]:[/] {scrutiny_result}")
            try:
                style = Style.from_dict({'prompt': 'ansicyan bold'})
                clarification = session.prompt("Provide clarification ❯ ", style=style).strip()
                if clarification:
                    user_input = f"{user_input}\n\nUser Clarification: {clarification}"
                else:
                    console.print("[dim]No clarification provided. Proceeding with original prompt...[/dim]")
            except (KeyboardInterrupt, EOFError):
                console.print("\n[bold red]Cancelled prompt.[/bold red]")
                continue

        # 2. Finalize Route (Apply HRF Checks)
        route = route_request(user_input, predefined_route=proposed_route)
        if route == "SWAP_RESTART":
            break
            
        console.print(f"[bold cyan]🔍 [Coordinator] Dispatching to: {route}[/]")
        
        # 3. Execute workflow
        try:
            execute_crew_workflow(route, user_input)
        except Exception as e:
            console.print(f"[bold red]Execution Error: {e}[/]")

if __name__ == "__main__":
    run_interactive_cli()
