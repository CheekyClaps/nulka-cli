# NulkaCLI

**An Enterprise Multi-Agent Workspace, built to run locally and save you money.**

*I was sick of the high costs associated with cloud-based AI CLI tools. So, I used AI to build NulkaCLI—a tool that puts local-first execution front and center, taming open-source models to perform like enterprise experts without the massive API bills.*

NulkaCLI is a terminal-based team of AI agents that work together to help you build, test, and secure your code. By running on your local machine using **Ollama**, you can load a model that perfectly fits your hardware. When a task gets too complex, NulkaCLI gracefully falls back to a "Universal Oracle" (like Gemini or Claude) to back up your local models.

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

NulkaCLI operates as a persistent shell. Open your terminal in your project folder, type `nulka-cli`, and ask for what you need in plain English:

> *"Please audit the current directory for hardcoded secrets and generate a compliance report."*

The semantic router will intercept this, recognize it as a security task, bypass the general assistant, and dispatch the Security Officer to execute a full audit.

### Essential Commands

* **`/risk <prompt>`** — Preview the hallucination risk score of a prompt before sending it.
* **`/hrf`** — View the current Hallucination Risk Factor threshold and trust settings.
* **`/teach`** — Triggers the feedback loop on the last query to permanently correct an agent's mistake using the Oracle.
* **`/oracle <query>`** — Bypass local models and directly query your external Universal Oracle.
* **`/models`** — Shows a list of all your local Ollama models.
* **`/pull <name>`**, **`/load <name>`**, **`/stop <name>`**, **`/rm <name>`** — Full lifecycle control over your Ollama models directly from the CLI.
* **`/expand`** — Opens the full, raw output of the last command in a full-screen pager (great for long code snippets).

---

## License

This project is licensed under the MIT License.