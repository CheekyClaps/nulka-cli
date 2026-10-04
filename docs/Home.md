# NulkaCLI Wiki

Welcome to the official Wiki for **NulkaCLI**, the Enterprise Multi-Agent Simulated Workspace.

## Table of Contents
1. [Core Architecture (Routing, HRF, Smart Edit)](Architecture.md)
2. [The Self-Learning Feedback Loop (Teacher & Oracle)](Learning-Loop.md)
3. [Customizing Agents & MCP Servers](Custom-Agents.md)

## Design Philosophy
NulkaCLI was built on the premise that prompt-engineering should be decoupled from python application logic. To achieve this, NulkaCLI uses a YAML/Markdown split configuration structure. 

All meta configurations are stored in YAML, while long-form instructions, personas, and dynamically updated rules are kept cleanly in Markdown files. 

### Why Local?
Running complex CrewAI swarms against paid APIs (OpenAI/Anthropic) will rapidly drain your wallet. NulkaCLI runs strictly local via Ollama (`qwen2.5` recommended). We offset the traditional weaknesses of local models through:
* **The `SmartEditTool`**: Decoupling file modification logic from pure reasoning to avoid placeholder bugs.
* **Safe Mode (`/plan`)**: Forcing agents to draft markdown plans before blindly modifying code.
* **Aggressive Backups (`/rewind`)**: Never destroying your workspace if an agent hallucination slips through. 
