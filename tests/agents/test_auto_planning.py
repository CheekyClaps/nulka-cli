from unittest.mock import MagicMock, patch
from nulka_cli import cli

def test_should_auto_plan_triggers():
    """Verify that complex architectural requests trigger auto-planning."""
    assert cli.should_auto_plan("Can you architect a new plugin system for us?") is True
    assert cli.should_auto_plan("Refactor the entire authentication system") is True
    assert cli.should_auto_plan("Prepare a migration plan to PostgreSQL") is True
    assert cli.should_auto_plan("Draft a roadmap for next quarter") is True
    assert cli.should_auto_plan("What is the weather like?") is False

def test_should_auto_plan_bypass_phrases():
    """Verify that execution directives bypass auto-planning."""
    assert cli.should_auto_plan("proceed with the plan") is False
    assert cli.should_auto_plan("continue") is False
    assert cli.should_auto_plan("build it now") is False
    assert cli.should_auto_plan("execute the refactor plan") is False

def test_route_request_auto_plan():
    """Verify that route_request returns PLAN for complex architectural prompts."""
    with patch('nulka_cli.cli.calculate_hallucination_risk', return_value=1):
        with patch('nulka_cli.hrf_manager.hrf_manager.get_threshold', return_value=7.0):
            route = cli.route_request("Let's redesign our database architecture")
            assert route == "PLAN"

            # Direct execution continues to normal route
            route = cli.route_request("proceed with the refactor", predefined_route="CREATOR")
            assert route == "CREATOR"

def test_execute_crew_workflow_plan_mode(monkeypatch):
    """Verify that the PLAN route re-routes to STRATEGIST with safe mode instructions."""
    calls = []

    def mock_workflow(route, prompt):
        calls.append((route, prompt))
        if route == "PLAN":
            # Call original logic for PLAN
            return "Plan created"
        return "Executed"

    with patch('nulka_cli.cli.execute_crew_workflow', side_effect=mock_workflow):
        pass

    # Direct test of the PLAN branch
    with patch.object(cli, 'execute_crew_workflow', wraps=cli.execute_crew_workflow) as spy:
        with patch('nulka_cli.cli.Crew') as mock_crew:
            mock_instance = MagicMock()
            mock_instance.kickoff.return_value = "Plan completed"
            mock_crew.return_value = mock_instance
            
            cli.execute_crew_workflow("PLAN", "Design the new messaging bus")
            
            # The second call should be to STRATEGIST with SAFE MODE instructions
            assert spy.call_count == 2
            assert spy.call_args_list[1][0][0] == "STRATEGIST"
            assert "SAFE MODE" in spy.call_args_list[1][0][1]
