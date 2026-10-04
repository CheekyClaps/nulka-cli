# 🏗 Core Architecture

NulkaCLI relies on the `crewai` and `langchain` frameworks to orchestrate its autonomous agents. 

## The Semantic Router & Pre-Execution Scrutiny
NulkaCLI implements an incredibly fast **Semantic Router** combined with a Scrutinizer.
1. **Pre-Execution Scrutiny**: A lightweight local LLM evaluates the prompt to ensure no critical context (like a filename) is missing. If it is, the router asks for clarification interactively.
2. **Lexical Fast-Path**: The router scans user input for predefined keywords (e.g. `firewall`, `port`, `refactor`). If a match is found, it routes instantly.
3. **Semantic Fallback**: If the prompt is ambiguous, the router uses a local LLM to classify the user's intent into predefined domains (`planner`, `architect`, `developer`, `tester`, etc.).

## Hallucination Risk Factor (HRF) Shield
To tame local open-source models, NulkaCLI evaluates every prompt for its "Hallucination Risk" (e.g., spatial reasoning, large data synthesis). 
* **Dynamic Temperature**: High-risk tasks lower the model's temperature automatically.
* **Auto-Oracle Routing**: If the score breaches a user-defined threshold, the task bypasses local execution and goes straight to the external Universal Oracle. (Adjustable via `/trust` and `/doubt`).

## The Universal Oracle
NulkaCLI operates primarily via **Ollama** running locally on the host machine to ensure strict data privacy. However, local models can occasionally hallucinate or lack external knowledge.

To solve this, NulkaCLI features a `Universal Oracle`. During the onboarding wizard, the system detects your installed CLI AI tools (like `gemini`, `claude`, or `chatgpt`) and exposes them as a fallback tool. If the local agents get stuck, they query the Oracle.

## Smart Edit Interpretation Layer
Traditional autonomous agents struggle with writing exact literal strings to replace code, often resulting in lazy placeholders (`... rest of code ...`). NulkaCLI solves this by decoupling reasoning from editing:
* The agent invokes the `SmartEditTool` with a target file and a natural language instruction.
* A specialized background LLM prompt acts as a pure "Interpretation Layer", outputting the complete, modified file block.
* Timestamped `.bak` files are automatically generated before any changes are committed to the filesystem, easily revertible via `/rewind`.

## Token Management & Memory Condensation
Terminal flooding and context-window exhaustion are aggressively managed:
* **Output Truncation**: Massive shell/tool outputs are instantly condensed in the terminal (viewable in full via `/expand`).
* **Memory Compression**: Users can type `/compress` to have the local LLM crush their entire active session history into a single, dense context paragraph, radically lowering token utilization on subsequent requests.

## Safe Mode Planning & MCP
* **`/plan`**: Enforces a strict "Safe Mode" where the `Architect` agent drafts a `plan.md` file based on codebase research without modifying any existing files.
* **`/mcp`**: NulkaCLI natively hooks into local Model Context Protocol (MCP) servers, granting local agents dynamic capabilities (like Jira querying or GitHub API access) without custom Python plugins.
