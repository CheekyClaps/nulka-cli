import pytest
from nulka_cli.utils import instantiate_agents


def test_agent_instantiation_and_roles():
    """Verify that all expected agents, including the new Ops Engineer, are instantiated."""
    agents = instantiate_agents()
    expected_keys = [
        "router", "assistant", "teacher", "external_oracle",
        "strategist", "creator", "auditor", "ops_engineer", "analyst"
    ]
    for key in expected_keys:
        assert key in agents, f"Expected agent '{key}' not found in instantiated agents."


def test_tool_isolation_boundaries():
    """Verify tool separation:
    - Creator has write tools, but no shell tool.
    - Auditor is strictly read-only.
    - Ops Engineer has shell tool, but no write tools.
    """
    agents = instantiate_agents()

    creator_tools = [t.name for t in agents["creator"].tools]
    auditor_tools = [t.name for t in agents["auditor"].tools]
    ops_tools = [t.name for t in agents["ops_engineer"].tools]

    # 1. Creator Verification
    assert "write_file" in creator_tools
    assert "search_replace" in creator_tools
    assert "smart_edit" in creator_tools
    assert "run_shell_command" not in creator_tools

    # 2. Auditor Verification (Strictly read-only)
    assert "read_file" in auditor_tools
    assert "grep_search" in auditor_tools
    assert "write_file" not in auditor_tools
    assert "search_replace" not in auditor_tools
    assert "smart_edit" not in auditor_tools
    assert "run_shell_command" not in auditor_tools

    # 3. Ops Engineer Verification (System admin)
    assert "run_shell_command" in ops_tools
    assert "write_file" not in ops_tools
    assert "search_replace" not in ops_tools
    assert "smart_edit" not in ops_tools


def test_strategist_delegation_enabled():
    """Verify that the Strategist is configured with allow_delegation=True to act as the manager."""
    agents = instantiate_agents()
    assert agents["strategist"].allow_delegation is True
    # Verify workers cannot delegate to prevent loops
    assert agents["creator"].allow_delegation is False
    assert agents["auditor"].allow_delegation is False
    assert agents["ops_engineer"].allow_delegation is False


def test_strategist_workflow_agents_contain_workers(monkeypatch):
    """Verify that executing the STRATEGIST route assembles a Crew containing worker agents for delegation."""
    from unittest.mock import MagicMock
    from nulka_cli import cli

    captured_crew = {}

    def mock_kickoff(self):
        captured_crew["agents"] = self.agents
        captured_crew["tasks"] = self.tasks
        return "Plan and delegation completed."

    monkeypatch.setattr(cli.Crew, "kickoff", mock_kickoff)
    monkeypatch.setattr(cli, "ollama_llm", MagicMock())

    cli.execute_crew_workflow("STRATEGIST", "is my ollama server optimized enough?")

    agent_roles = [a.role for a in captured_crew["agents"]]
    # The Strategist must have access to Ops Engineer, Creator, Auditor, Analyst in its crew
    agents_dict = instantiate_agents()
    assert agents_dict["strategist"].role in agent_roles
    assert agents_dict["ops_engineer"].role in agent_roles
    assert agents_dict["creator"].role in agent_roles
    assert agents_dict["auditor"].role in agent_roles
    assert agents_dict["analyst"].role in agent_roles

