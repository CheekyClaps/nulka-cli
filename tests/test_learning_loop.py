import sys
import os
import unittest
from unittest.mock import patch

# Add workspace root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestLearningLoop(unittest.TestCase):
    def test_teacher_tool_execution(self):
        """Verifies that the InteractiveTeacherTool can execute and append rules correctly."""
        from nulka_cli.tools.interactive_teacher_tool import InteractiveTeacherTool
        
        tool = InteractiveTeacherTool()
        
        # Read the original content of assistant.md using an absolute path to match tool logic
        assistant_path = os.path.abspath("nulka_cli/config/agents/assistant.md")
        with open(assistant_path, "r") as f:
            original_content = f.read()
            
        try:
            # We mock 'ask_user_safe' to simulate user accepting the rules,
            # (Git commit logic was removed from the tool for security)
            with patch('nulka_cli.core.state.ask_user_safe', return_value="a"):
                 
                # Run the tool on assistant backstory
                result = tool._run(agent_name="assistant", proposed_rules="Always state that you are a highly helpful and friendly assistant.")
                
                self.assertIn("permanently updated", result)
                self.assertTrue(os.path.exists(assistant_path))
                
                # Read assistant.md to verify it appended the rules
                with open(assistant_path, "r") as f:
                    content = f.read()
                self.assertIn("Always state that you are a highly helpful and friendly assistant.", content)
                
        finally:
            # Restore the original file content
            with open(assistant_path, "w") as f:
                f.write(original_content)

    def test_consult_oracle_tool(self):
        """Verifies that the ConsultOracleTool executes correctly."""
        from nulka_cli.tools.consult_oracle_tool import ConsultOracleTool
        
        tool = ConsultOracleTool()
        
        # Mock OracleCLITool._run to return a predictable response
        with patch('nulka_cli.tools.oracle_cli_tool.OracleCLITool._run', return_value="Oracle Answer"):
            result = tool._run("What is 2+2?")
            self.assertEqual(result, "Oracle Answer")

    def test_execute_teach_feedback_oracle_fail(self):
        """Verifies that execute_teach_feedback handles Oracle failures by prompting for manual rules."""
        from nulka_cli.cli import execute_teach_feedback
        from nulka_cli.core.state import state
        
        # Save original state
        orig_prompt = state.last_user_prompt
        orig_route = state.last_route
        
        try:
            state.last_user_prompt = "some query"
            state.last_route = "GENERAL"
            
            # Patch OracleCLITool._run to return an error/timeout string
            # Patch ask_user_safe to return our custom rule
            # Patch doubt to return a float (5.0) so format formatting :.2f doesn't fail on MagicMock
            with patch('nulka_cli.tools.oracle_cli_tool.OracleCLITool._run', return_value="Error: Oracle CLI query timed out after 120 seconds."), \
                 patch('nulka_cli.core.state.ask_user_safe', return_value="My custom manual rule") as mock_ask, \
                 patch('nulka_cli.tools.interactive_teacher_tool.InteractiveTeacherTool._run', return_value="Success") as mock_teacher_run, \
                 patch('nulka_cli.cli.hrf_manager.doubt', return_value=5.0) as mock_doubt:
                 
                execute_teach_feedback()
                
                # Check that fallback input was called
                mock_ask.assert_called_once()
                # Check that InteractiveTeacherTool._run was called with the custom rule we entered!
                mock_teacher_run.assert_called_once_with(
                    agent_name="assistant",
                    proposed_rules="When faced with requests similar to 'some query', apply the following universal guideline:\nMy custom manual rule\nAlways ensure this rule is applied abstractly to the current context."
                )
                # Check that doubt was called
                mock_doubt.assert_called_once()
                
        finally:
            state.last_user_prompt = orig_prompt
            state.last_route = orig_route

    def test_execute_teach_feedback_oracle_success(self):
        """Verifies that execute_teach_feedback uses Oracle answer directly when successful."""
        from nulka_cli.cli import execute_teach_feedback
        from nulka_cli.core.state import state
        
        orig_prompt = state.last_user_prompt
        orig_route = state.last_route
        
        try:
            state.last_user_prompt = "another query"
            state.last_route = "CREATOR"

            # Patch hrf_manager.doubt to return 5.0 to support :.2f float formatting
            with patch('nulka_cli.tools.oracle_cli_tool.OracleCLITool._run', return_value="Oracle solution here"), \
                 patch('nulka_cli.tools.interactive_teacher_tool.InteractiveTeacherTool._run', return_value="Success") as mock_teacher_run, \
                 patch('nulka_cli.cli.hrf_manager.doubt', return_value=5.0) as mock_doubt:

                execute_teach_feedback()

                mock_teacher_run.assert_called_once_with(
                    agent_name="creator",
                    proposed_rules="When faced with requests similar to 'another query', apply the following universal guideline:\nOracle solution here\nAlways ensure this rule is applied abstractly to the current context."
                )
                mock_doubt.assert_called_once()
                
        finally:
            state.last_user_prompt = orig_prompt
            state.last_route = orig_route

if __name__ == "__main__":
    unittest.main()
