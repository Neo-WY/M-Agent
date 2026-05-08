from m_agent.agents.memory_agent.answerability import llm_judge_direct
from m_agent.agents.memory_agent.core import MemoryAgent
from m_agent.agents.memory_agent.workspace import Workspace


def main() -> None:
    agent = MemoryAgent("config/agents/memory/locomo_eval_memory_agent_full_mode_E2.yaml")
    ws = Workspace(max_keep=3)
    ws.original_question = "Q?"
    ws.cur_query = "Q?"
    ws.extend_and_track_new(
        [
            {
                "evidence_id": "EVID1",
                "source_type": "test",
                "content": "Some info",
            }
        ]
    )

    prompt = agent._build_workspace_direct_judge_prompt(ws)
    assert "useful_information" in prompt
    assert "<original_question>" not in prompt

    out = llm_judge_direct(
        llm_func=lambda _: '{"useful_information":"k","answer":"a","next_query":"n"}',
        prompt_text="x",
    )
    assert out["answer"] == "a"
    assert out["next_query"] is None

    out2 = llm_judge_direct(
        llm_func=lambda _: '{"useful_information":"k","answer":null,"next_query":"n"}',
        prompt_text="x",
    )
    assert out2["answer"] is None
    assert out2["next_query"] == "n"

    print("direct_judge_smoke_ok")


if __name__ == "__main__":
    main()

