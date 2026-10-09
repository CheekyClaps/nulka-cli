# 🤖 NulkaCLI

**An Enterprise Multi-Agent Local Workspace powered by Ollama, Textual, and CrewAI.**

*Run an elite, specialized crew of autonomous AI agents locally on your own hardware without draining your wallet on cloud API subscriptions.*

NulkaCLI transforms your terminal into an interactive, multi-agent development environment. Using **Ollama** for local inference, it routes your requests to dedicated agent departments (`Strategist`, `Creator`, `Auditor`, `Ops Engineer`, `Analyst`, `Assistant`, `Teacher`), streams real-time tool executions, and dynamically falls back to a **Universal Oracle** (e.g. Gemini, Claude, or ChatGPT) when high-risk hallucinations or gaps in knowledge are detected.

---

## ✨ Key Capabilities

* **Modern Textual Terminal UI (Default):** Launches into an asynchronous, non-blocking terminal workspace featuring collapsible action and reasoning drawers, a Vim-navigable directory tree, and selectable log modals.
* **Strict Tool Boundaries (Functional Isolation):**
  * `The Creator`: Exclusive file mutation rights (`write_file`, `search_replace`, `smart_edit`).
  * `The Ops Engineer`: Exclusive shell and POSIX pseudo-terminal execution rights (`run_shell_command`).
  * `The Auditor`: Deep read-only security and code audits.
  * `The Strategist`: Project planning and safe-mode delegation (`plan.md`).
  * `The Assistant`: The unified conversational voice and reporter for all specialist deliverables.
* **Live Tool & Thought Streaming:**
  * **Live Action Drawer (`Ctrl+D`)**: Streams POSIX PTY shell commands and filesystem actions with real-time ANSI coloring.
  * **Model Thought Drawer (`Ctrl+T`)**: Streams agent reasoning and inner monologues.
  * **Selectable Logs Modal (`Ctrl+L`)**: Opens full-screen, copyable text views of both streams without terminal mouse capture interference.
* **Shared Memory File Cache ("The Blackboard"):** Automatically caches recently modified workspace files in memory, allowing the Assistant to answer follow-up questions about newly created reports and scripts without re-reading tools.
* **Self-Learning Feedback Loop (`/teach`):** When an agent fails, trigger `/teach` to query the Universal Oracle, extract an abstract "Lesson Learned", and permanently write the rule into the agent's backstory in Git.
* **Hallucination Risk Factor (HRF):** Evaluates prompts before running, dynamically adjusting LLM temperature, triggering multi-agent peer reviews, or routing directly to the Oracle.

---

## 🚀 Getting Started

### Prerequisites
1. **Python 3.10+**
2. **Ollama** installed and running (`ollama serve`) with your model of choice (recommended: `qwen2.5:14b` or `deepseek-r1:14b`).
3. *(Optional)* A globally installed CLI AI tool (e.g., `gemini-cli`) for Oracle fallback.

### Installation

Clone and install in editable mode:

```bash
git clone https://github.com/cheekyclaps/nulka-cli.git
cd nulka-cli
pip install -e .
```

### Running NulkaCLI

Launch the modern Textual TUI:
```bash
nulka_cli
```

Or run in classic REPL mode:
```bash
nulka_cli --repl
```

---

## ⌨️ TUI Keyboard Shortcuts

| Shortcut | Description |
| :--- | :--- |
| **`Ctrl+B`** | Toggle the Workspace File Tree sidebar (closed by default) |
| **`Ctrl+D`** | Toggle the Live Action Drawer (tool streaming) |
| **`Ctrl+T`** | Toggle the Model Thought Drawer (agent reasoning) |
| **`Ctrl+L`** | Open the full-screen selectable **Stream Logs Modal** for easy copying |
| **`Ctrl+Y`** | Silently copy the last agent output to system clipboard |
| **`Backspace` / `h`** | Inside the Workspace Tree, navigate up to parent directory (Vim-style) |
| **`F1`** | Show built-in help and command cheatsheet |

---

## 📚 Command Reference

NulkaCLI includes a comprehensive set of slash commands available in both TUI and REPL modes:

### Core & Navigation
* **`/help`** or **`/?`** — Display interactive help and command list
* **`/clear`** — Clear active chat log and session buffers
* **`/copy`** — Copy the latest response to clipboard
* **`/rewind`** — Undo the last conversational turn and offer to restore `.bak` files
* **`/quit`** — Exit session cleanly

### Agent & Workflow Management
* **`/plan <goal>`** — Engage Safe Mode Planning: Strategist drafts `plan.md` using read-only tools
* **`/teach`** — Consult Oracle to generate a permanent rule from the last failed turn
* **`/memory`** — View compressed session memory and all learned agent rules
* **`/agents`** — Display status of all active agent departments
* **`/tools`** — List all available agent capabilities and assignments
* **`/oracle <query>`** — Directly query the configured fallback AI CLI

### Model & Risk Tuning
* **`/models`** — List downloaded and active Ollama models
* **`/pull <name>`** — Download a model from Ollama Library
* **`/load <name>`** — Load a model into memory and persist as active
* **`/hrf`** — Show current Hallucination Risk Factor threshold
* **`/trust`** / **`/doubt`** — Manually raise or lower the model trust threshold

---

## 🧪 Running the Test Suite

The test suite is structured cleanly into modular domains:

```bash
# Run all tests
pytest tests/

# Run specific categories
pytest tests/agents/     # Agent prompts, topology, auto-planning
pytest tests/frontend/   # TUI interface, slash commands, integration
pytest tests/tools/      # PTY shell, smart edit, search replace, fs tools
pytest tests/core/       # HRF manager, self-learning loop
```

---

## 📄 License

This project is licensed under the MIT License.