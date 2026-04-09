"""
Unit test for MultiAgentDebateAgent.
Mocks the 3 sub-agent LLM calls and verifies DebateOutput parses and validates correctly.
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.models import (
    DebateOutput, OptimistStance, RealistStance, CriticStance, DebateVerdict
)
from src.agents.multi_agent_debate import MultiAgentDebateAgent


# ─── Fixtures ─────────────────────────────────────────────────────────────────

MOCK_OPTIMIST_JSON = json.dumps({
    "recommended_path": "Software Engineer -> ML Engineer via Python specialization",
    "rationale": "Strong Python background enables rapid transition within 12 months.",
    "key_bets": ["Complete a production ML project in 3 months", "Contribute to open-source ML libraries"]
})

MOCK_REALIST_JSON = json.dumps({
    "recommended_path": "Software Engineer -> Data Analyst -> ML Engineer",
    "rationale": "Incremental path with clear compensation preservation at each step.",
    "key_bets": ["Take internal data projects", "Get AWS ML certification first"]
})

MOCK_CRITIC_JSON = json.dumps({
    "risks": ["ML Engineer roles require deep research background that a 12-month plan may underestimate"],
    "red_flags": ["No Masters degree may be a dealbreaker at top-tier companies", "Computer vision competition is high in the current job market"]
})

MOCK_VERDICT_JSON = json.dumps({
    "consensus_path": "Software Engineer -> ML Engineer with Python specialization and AWS certification milestone",
    "confidence": 0.72,
    "reasoning": "Optimist and Realist agree on Python as the specialization vector. Critic's risk about research background addressed by adding a certification milestone.",
    "debate_rounds": 2
})

MOCK_CAREER_PATHS = {
    "recommended_paths": [{"path_description": "ml_engineer", "avg_reachability": 0.52}],
    "reasoning": "Based on graph data, ml_engineer is the top match.",
    "data_gaps": ["No explicit cv data"]
}


# ─── Test Class ────────────────────────────────────────────────────────────────

class TestMultiAgentDebateAgent:

    def _make_agent(self):
        mock_llm = MagicMock()
        # generate is called as an awaitable
        mock_llm.generate = AsyncMock(side_effect=[
            MOCK_OPTIMIST_JSON,
            MOCK_REALIST_JSON,
            MOCK_CRITIC_JSON,
            MOCK_VERDICT_JSON,
        ])
        return MultiAgentDebateAgent(mock_llm)

    def test_debate_output_model_validates_correctly(self):
        """DebateOutput Pydantic model validates correctly from real-looking data."""
        output = DebateOutput(
            optimist_stance=OptimistStance(
                recommended_path="Fast path",
                rationale="Lots of momentum",
                key_bets=["Bet A", "Bet B"]
            ),
            realist_stance=RealistStance(
                recommended_path="Safe path",
                rationale="Stable",
                key_bets=["Step A"]
            ),
            critic_stance=CriticStance(
                risks=["Risk 1"],
                red_flags=["Flag 1"]
            ),
            final_verdict=DebateVerdict(
                consensus_path="Consensus path",
                confidence=0.75,
                reasoning="Agreed on Python",
                debate_rounds=2
            )
        )
        assert output.final_verdict.confidence == 0.75
        d = output.model_dump()
        assert "optimist_stance" in d
        assert "realist_stance" in d
        assert "critic_stance" in d
        assert "final_verdict" in d

    @pytest.mark.asyncio
    async def test_run_returns_debate_result_with_valid_structure(self):
        """run() calls 3 sub-agents concurrently and returns debate_result dict."""
        agent = self._make_agent()

        # Build a mock CareerPathOptions-like object
        mock_career_paths = MagicMock()
        mock_career_paths.model_dump.return_value = MOCK_CAREER_PATHS

        state = {
            "career_paths": mock_career_paths,
            "completed_agents": [],
            "errors": [],
        }

        result = await agent.run(state)

        assert "debate_result" in result
        debate = result["debate_result"]
        assert "optimist_stance" in debate
        assert "realist_stance" in debate
        assert "critic_stance" in debate
        assert "final_verdict" in debate

    @pytest.mark.asyncio
    async def test_run_gracefully_handles_missing_career_paths(self):
        """run() returns empty dict (graceful pass-through) when career_paths is missing."""
        agent = self._make_agent()
        state = {"completed_agents": [], "errors": []}
        result = await agent.run(state)
        assert result == {}

    @pytest.mark.asyncio
    async def test_run_returns_fallback_on_llm_failure(self):
        """run() returns a fallback DebateOutput when LLM calls fail with an exception."""
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(side_effect=Exception("LLM is down"))
        agent = MultiAgentDebateAgent(mock_llm)

        mock_career_paths = MagicMock()
        mock_career_paths.model_dump.return_value = MOCK_CAREER_PATHS

        state = {"career_paths": mock_career_paths, "completed_agents": [], "errors": []}
        result = await agent.run(state)

        # Should return debate_result with fallback, not crash
        assert "debate_result" in result
        fallback = result["debate_result"]
        # When all LLM calls fail, synthesizer uses its heuristic fallback (0.4)
        # which is still low confidence — confirm it's below 0.5
        assert fallback["final_verdict"]["confidence"] < 0.5
