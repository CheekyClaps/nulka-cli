# NulkaCLI

**An Enterprise Multi-Agent Workspace, built to run locally and save you money.**

*I was sick of the high costs associated with cloud-based AI CLI tools. So, I used AI to build NulkaCLI—a tool that puts local-first execution front and center, taming open-source models to perform like enterprise experts without the massive API bills.*

NulkaCLI is not just for code—it is a comprehensive, general-purpose terminal assistant. It functions as a team of AI agents that work together to manage your daily workflow, automate system tasks, analyze data, and naturally, help you build, test, and secure your code. By running on your local machine using **Ollama**, you can load a model that perfectly fits your hardware. When a task gets too complex, NulkaCLI gracefully falls back to a "Universal Oracle" (like Gemini or Claude) to back up your local models.

---

## ✨ Key Features

* **Local-First with Oracle Fallback:** Runs entirely on your hardware via Ollama. If a prompt triggers the risk threshold, the system automatically routes the request to your configured Oracle (an external AI CLI) to handle the heavy lifting.
* **Powered by CrewAI & LangChain:** Built on robust frameworks, giving agents access to nifty custom tools. It's incredibly easy to build new agents, delegate tasks, and execute complex filesystem operations.
* **Live Agent Teaching (`/teach`):** If a local model hallucinates or fails a task, simply type `/teach`. NulkaCLI will consult the Oracle for the correct answer, extract a universal "Lesson Learned," and permanently update the local agent's rulebook. 
* **Taming Local Models (HRF & Temperature):** Local models are prone to hallucination. NulkaCLI solves this using the **Hallucination Risk Factor (HRF)**. It dynamically scores your prompt's risk, automatically scales the model's temperature (e.g., dropping to 0.0 for strict tasks), and even injects a **Fact-Checker Agent** to cross-examine drafted answers before you see them.

---

## 🚀 Getting Started

### Prerequisites
1. **Python 3.10+**
2. **Ollama** installed and running in the background ([ollama.com](https://ollama.com)).
3. *(Optional but Recommended)* A globally installed AI CLI tool (like `gemini-cli`) to act as your fallback Oracle.

### Installation

Clone the repository and install it in editable mode (required so agent rules can update dynamically via the teaching loop):

```bash
git clone https://github.com/cheekyclaps/nulka-cli.git
cd nulka-cli
pip install -e .
```

Boot it up:

```bash
nulka-cli
```

*On your first run, a beautiful onboarding wizard will help you link your Oracle command.*

---

## 💬 How to use it

NulkaCLI operates as a persistent shell. Open your terminal anywhere, type `nulka-cli`, and ask for what you need in plain English:

> *"Please audit the current directory for hardcoded secrets and generate a compliance report."*

> *"Organize these downloaded PDFs into folders by year, and summarize the contents of the latest one."*

The semantic router will intercept this, recognize the intent, bypass the general assistant, and dispatch the correct specialized agent to execute the task.

### 📚 Command Reference

NulkaCLI includes a rich set of built-in slash commands to manage your workspace, models, and agents.

#### Core System
* **`/about`** — Show NulkaCLI version and diagnostic info
* **`/clear`** — Clear the screen and reset session context
* **`/vim`** — Toggle Vim-mode keybindings for the prompt
* **`/quit`** — Exit session (use `--delete` to purge history)

#### Tools, Output, & Agents
* **`/expand`** — View the last truncated output in a full-screen pager
* **`/copy`** — Copy the last raw output to your clipboard
* **`/tools`** — List available capabilities
* **`/agents`** — List available specialized AI departments
* **`/oracle <query>`** — Directly query the External Universal Oracle
* **`/metrics`** — Toggle the live bottom toolbar for performance metrics
* **`/debug`** — Toggle verbose agent thoughts & details

#### Workspace & Directory Management
* **`/cd [path]`** — Change current working directory
* **`/pwd`** — Show current working directory path
* **`/ls [path]`** — List contents of a directory (defaults to current)
* **`/workspace [cmd]`** — Manage active directories (subcmds: show, add, set)

#### Learning & Trust (HRF)
* **`/teach`** — Flag the last response as incomplete & teach the agent
* **`/hrf`** — Show current Hallucination Risk Factor settings
* **`/risk <prompt>`** — Preview the hallucination risk score of a prompt
* **`/trust`** — Trust model more (raises Oracle threshold)
* **`/doubt`** — Trust model less (lowers Oracle threshold)
* **`/bs [weight]`** — Apply hallucination penalty to drop trust
* **`/forgive`** — Reset trust back to clean-slate baseline

#### Model Management
* **`/models`** — Show downloaded & loaded Ollama models
* **`/pull <name>`** — Download a new model from the Ollama library
* **`/load <name>`** — Load a model into memory
* **`/stop <name>`** — Stop a running model
* **`/rm <name>`** — Remove a model from the system

---

## License

This project is licensed under the MIT License.