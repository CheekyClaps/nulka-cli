import pytest
from nulka_cli.utils import instantiate_agents

def test_no_delegation_hallucination_instructions():
    """Verify that worker agents are explicitly instructed NOT to hallucinate delegation."""
    agents = instantiate_agents()
    
    # These agents do NOT have delegation capabilities and MUST be explicitly told not to fake it.
    workers = ["creator", "ops_engineer", "auditor", "analyst", "assistant"]
    
    for worker_name in workers:
        agent = agents[worker_name]
        prompt = agent.backstory.lower()
        
        # Ensure the prompt contains explicit anti-delegation constraints
        assert "delegate" in prompt or "delegation" in prompt, \
            f"{worker_name} missing explicit instructions against hallucinating delegation."
            
        assert "do not hallucinate" in prompt or "cannot delegate tasks" in prompt or "not have the ability to delegate" in prompt, \
            f"{worker_name} missing explicit instructions against hallucinating delegation."

def test_creator_exclusive_file_creation():
    """Verify the Creator is explicitly instructed that it is the sole file modifier."""
    agents = instantiate_agents()
    creator_prompt = agents["""creator"""].backstory.lower()
    
    assert "sole file modifier" in creator_prompt or "sole agent permitted to write" in creator_prompt
    assert "write_file" in creator_prompt
