import os
import platform
import time
from datetime import datetime

import yaml
from crewai import Agent
from langchain_community.llms import Ollama

from nulka_cli.tools.consult_oracle_tool import ConsultOracleTool
from nulka_cli.tools.fs_tools import (
    GlobSearchTool,
    GrepSearchTool,
    ListDirectoryTool,
    ReadFileTool,
    SearchReplaceTool,
    SmartEditTool,
    WriteFileTool,
)
from nulka_cli.tools.interactive_teacher_tool import InteractiveTeacherTool
from nulka_cli.tools.oracle_cli_tool import OracleCLITool
from nulka_cli.tools.shell_tool import RunShellCommandTool
from nulka_cli.tools.ui_tools import AskUserTool, UpdateTopicTool
from nulka_cli.tools.web_fetch_tool import WebFetchTool
from nulka_cli.tools.web_search_tool import WebSearchTool

# (Moved logic to bottom of file)

def get_system_context():
    """Gathers real-time environmental context metrics for the Router agent."""
    # 1. System Time
    now = datetime.now()
    current_time = now.strftime("%A, %B %d, %Y - %I:%M:%S %p")
    
    # 2. Operating System Details
    system_os = platform.system()
    system_platform = platform.platform()
    
    linux_distro = "N/A"
    package_manager = "N/A"
    if system_os == "Linux":
        try:
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release") as f:
                    for line in f:
                        if line.startswith("PRETTY_NAME="):
                            linux_distro = line.split("=")[1].strip().strip('"')
                            break
        except Exception:
            pass
            
        import shutil
        if shutil.which("dnf"):
            package_manager = "dnf (Fedora/RHEL)"
        elif shutil.which("apt-get") or shutil.which("apt"):
            package_manager = "apt (Debian/Ubuntu)"
        elif shutil.which("pacman"):
            package_manager = "pacman (Arch)"
        elif shutil.which("zypper"):
            package_manager = "zypper (openSUSE)"
        elif shutil.which("apk"):
            package_manager = "apk (Alpine)"
    
    # 3. Geolocation via System Timezone Info
    timezone = "UTC"
    try:
        if os.path.exists("/etc/timezone"):
            with open("/etc/timezone", "r") as f:
                timezone = f.read().strip()
        elif hasattr(time, "tzname"):
            timezone = "/".join(time.tzname)
    except Exception:
        pass
        
    return {
        "current_time": current_time,
        "system_os": system_os,
        "system_platform": system_platform,
        "linux_distro": linux_distro,
        "package_manager": package_manager,
        "geolocation": timezone,
        "working_directory": os.getcwd()
    }

def load_agent_configs(agents_yaml_path="config/agents.yaml"):
    """Loads agents.yaml and pre-injects backstories from linked .md files."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    agents_yaml_path = os.path.join(base_dir, agents_yaml_path)

    if not os.path.exists(agents_yaml_path):
        raise FileNotFoundError(f"Configuration file not found: {agents_yaml_path}")
        
    with open(agents_yaml_path, "r") as f:
        agents_data = yaml.safe_load(f)
        
    context = get_system_context()
    
    # Load Universal Ground Rules (Anti-Trap Directives) natively
    ground_rules = ""
    rules_path = os.path.join(base_dir, "config", "universal_directives.md")
    
    # Also support user-level global overrides if they exist
    global_rules_path = os.path.expanduser("~/.nulka_cli_rules.md")
    
    combined_rules = []
    
    if os.path.exists(rules_path):
        try:
            with open(rules_path, "r") as f:
                content = f.read().strip()
                if content:
                    combined_rules.append(content)
        except Exception:
            pass
            
    if os.path.exists(global_rules_path):
        try:
            with open(global_rules_path, "r") as f:
                content = f.read().strip()
                if content:
                    combined_rules.append(f"### 👤 User Global Overrides\n{content}")
        except Exception:
            pass
            
    if combined_rules:
        ground_rules = "\n\n" + "\n\n".join(combined_rules)
    
    for agent_config in agents_data.values():
        backstory_file = agent_config.get("backstory_file")
        if backstory_file:
            # Resolve relative path safely
            backstory_file = os.path.join(base_dir, backstory_file.strip())
            if os.path.exists(backstory_file):
                with open(backstory_file, "r") as bf:
                    raw_backstory = bf.read()
                # Dynamically inject system variables into the backstory
                try:
                    formatted_backstory = raw_backstory.format(
                        system_os=context["system_os"],
                        system_platform=context["system_platform"],
                        linux_distro=context["linux_distro"],
                        package_manager=context["package_manager"],
                        current_time=context["current_time"],
                        geolocation=context["geolocation"],
                        working_directory=context.get("working_directory", os.getcwd())
                    )
                except KeyError:
                    # Fallback in case the markdown contains other curly brace patterns
                    # We only replace known variables
                    formatted_backstory = raw_backstory
                    for var in ["system_os", "system_platform", "linux_distro", "package_manager", "current_time", "geolocation", "working_directory"]:
                        formatted_backstory = formatted_backstory.replace(f"{{{var}}}", str(context.get(var, "")))
                
                # Inject universal ground rules
                if ground_rules:
                    formatted_backstory += ground_rules
                
                agent_config["backstory"] = formatted_backstory
            else:
                agent_config["backstory"] = "Backstory markdown file not found."
                
    return agents_data

def instantiate_agents(custom_tools=None):
    """Instantiates and returns the dictionary of initialized CrewAI Agent objects."""
    if custom_tools is None:
        custom_tools = []
        
    # Standardize our local Oracle CLI Tool
    oracle_cli_tool = OracleCLITool()
    interactive_teacher_tool = InteractiveTeacherTool()
    consult_oracle_tool = ConsultOracleTool()
    web_search_tool = WebSearchTool()
    web_fetch_tool = WebFetchTool()
    
    # Workspace & File System Tools
    read_tool = ReadFileTool()
    write_tool = WriteFileTool()
    search_replace_tool = SearchReplaceTool()
    smart_edit_tool = SmartEditTool()
    list_dir_tool = ListDirectoryTool()
    glob_tool = GlobSearchTool()
    grep_tool = GrepSearchTool()
    shell_tool = RunShellCommandTool()

    # UI/Interactive Tools for Managers
    ask_user_tool = AskUserTool()
    update_topic_tool = UpdateTopicTool()

    configs = load_agent_configs()
    agents = {}

    # Distribute tools to relevant agents
    for agent_key, config in configs.items():
        # Setup tools for each agent based on their requirements

        # 1. Base Exploration Suite (Permissive reading & search for all core agents)
        if agent_key == "external_oracle":
            agent_tools = [oracle_cli_tool]
        else:
            agent_tools = [
                web_search_tool, web_fetch_tool, 
                read_tool, list_dir_tool, glob_tool, grep_tool
            ]

        # 2. Strict Role-Specific Tool Assignments
        if agent_key == "creator":
            # Exclusive file modification rights (both fast search-replace and complex smart-edit)
            agent_tools.extend([write_tool, search_replace_tool, smart_edit_tool])
            
        elif agent_key == "ops_engineer":
            # Exclusive shell execution rights
            agent_tools.append(shell_tool)
            
        elif agent_key in ["strategist", "router"]:
            # Management and user interaction suite
            agent_tools.extend([ask_user_tool, update_topic_tool])
            
        elif agent_key == "assistant":
            # General companion gets fallback oracle access
            agent_tools.append(oracle_cli_tool)
            
        elif agent_key == "teacher":
            # Educational director gets teaching & oracle consultation tools
            agent_tools.extend([interactive_teacher_tool, consult_oracle_tool])
            
        # Give workspace access tools if passed, BUT explicitly deny them to external_oracle
        if custom_tools and agent_key != "external_oracle":
            agent_tools.extend(custom_tools)
            
        # Managers allowed to delegate tasks to others
        allow_delegation = agent_key in ["router", "strategist"]
        
        # Use Fast model for planning/routing/analysis to speed up processing
        # Use heavy main model for coding/writing (creator, ops)
        agent_llm = ollama_fast_llm if agent_key in ["router", "strategist", "analyst", "assistant"] else ollama_llm
            
        agents[agent_key] = Agent(
            role=config["role"],
            goal=config["goal"],
            backstory=config["backstory"],
            verbose=True,
            allow_delegation=allow_delegation,
            tools=agent_tools,
            llm=agent_llm,
            max_iter=30,  # Increased cap to allow for multi-document research
            max_execution_time=600 # 10 minute timeout
        )
        
    return agents

def is_ollama_running(url="http://localhost:11434"):
    """Checks if the local Ollama server is running and responding."""
    import requests
    try:
        response = requests.get(url, timeout=2)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def start_ollama_server():
    """Starts the local Ollama server in the background."""
    import subprocess

    if is_ollama_running():
        return True, "Ollama is already running."
        
    try:
        # Start 'ollama serve' in background
        # We redirect stdout/stderr to devnull to prevent blocking or terminal spam
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True
        )
        
        # Poll the server until it responds (max 15 seconds)
        for _ in range(15):
            time.sleep(1)
            if is_ollama_running():
                return True, "Ollama server started successfully."
        return False, "Failed to start Ollama server (timeout expired)."
    except Exception as e:
        return False, f"Error starting Ollama server: {e}"

def get_local_models():
    """Queries the local Ollama API to list all installed/downloaded models."""
    import requests
    if not is_ollama_running():
        return []
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=3)
        if response.status_code == 200:
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        pass
    return []

def get_loaded_models():
    """Queries the local Ollama API to list currently active/loaded models in memory."""
    import requests
    if not is_ollama_running():
        return []
    try:
        response = requests.get("http://localhost:11434/api/ps", timeout=3)
        if response.status_code == 200:
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        pass
    return []

# Setup standard local LLM
# Allow user to override the default model via ~/.nulka_cli_env (e.g. LOCAL_MODEL="llama3.1")
def get_best_available_model() -> str:
    """Intelligently determines the best model to use at startup."""
    # 1. Check if user explicitly set an environment variable
    env_model = os.getenv("LOCAL_MODEL")
    if env_model and env_model != "unknown":
        return env_model

    # 2. Check what is currently loaded in memory
    loaded = get_loaded_models()
    if loaded:
        return loaded[0]

    # 3. Check what is downloaded/available locally
    local = get_local_models()
    if local:
        return local[0]

    # 4. Total fallback (will likely cause a 404 if not pulled, but avoids crashing on boot)
    return "unknown"

def get_fast_model() -> str:
    """Returns a fast, smaller model for routing and simple chats (e.g. 7B/8B)."""
    fast_env = os.getenv("LOCAL_FAST_MODEL")
    if fast_env and fast_env != "unknown":
        return fast_env

    # Auto-detect a smaller model if available
    local = get_local_models()
    for m in local:
        if "7b" in m.lower() or "8b" in m.lower() or "mini" in m.lower():
            return m

    # Fallback to the primary model
    return get_best_available_model()

# Initialize with the best guess at boot. 
# We update it dynamically before critical calls if needed.
local_model_name = get_best_available_model()
fast_model_name = get_fast_model()

ollama_llm = Ollama(model=local_model_name, base_url="http://localhost:11434")
ollama_fast_llm = Ollama(model=fast_model_name, base_url="http://localhost:11434")


def copy_text_to_clipboard(text: str) -> bool:
    """Robust cross-platform clipboard copy function.
    Supports wl-copy (Wayland), xsel/xclip (X11), pbcopy (macOS), and pyperclip.
    """
    import shutil
    import subprocess

    # 1. Wayland clipboard
    if shutil.which("wl-copy"):
        try:
            subprocess.run(["wl-copy"], input=text.encode("utf-8"), check=True, timeout=2)
            return True
        except Exception:
            pass

    # 2. X11 clipboard via xsel
    if shutil.which("xsel"):
        try:
            subprocess.run(["xsel", "-b", "-i"], input=text.encode("utf-8"), check=True, timeout=2)
            return True
        except Exception:
            pass

    # 3. X11 clipboard via xclip
    if shutil.which("xclip"):
        try:
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode("utf-8"), check=True, timeout=2)
            return True
        except Exception:
            pass

    # 4. macOS clipboard
    if shutil.which("pbcopy"):
        try:
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True, timeout=2)
            return True
        except Exception:
            pass

    # 5. Fallback to pyperclip if installed
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        pass

    return False


def get_vram_usage() -> float | None:
    """Returns VRAM usage as a float between 0.0 and 1.0. Supports AMD (rocm-smi) and NVIDIA (nvidia-smi)."""
    import subprocess
    import json
    
    # Try AMD
    try:
        res = subprocess.run(['rocm-smi', '--showmeminfo', 'vram', '--json'], capture_output=True, text=True, timeout=1)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            for gpu in data.values():
                total = int(gpu.get('VRAM Total Memory (B)', 0))
                used = int(gpu.get('VRAM Total Used Memory (B)', 0))
                if total > 0:
                    return used / total
    except Exception:
        pass
        
    # Try NVIDIA
    try:
        res = subprocess.run(['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=1)
        if res.returncode == 0:
            parts = res.stdout.strip().split('\n')[0].split(',')
            used = int(parts[0].strip())
            total = int(parts[1].strip())
            if total > 0:
                return used / total
    except Exception:
        pass
        
    return None

def get_vram_status_string() -> str:
    """Returns a formatted string like 'VRAM: 85%' or empty if unavailable."""
    usage = get_vram_usage()
    if usage is not None:
        pct = int(usage * 100)
        return f"VRAM: {pct}%"
    return ""


