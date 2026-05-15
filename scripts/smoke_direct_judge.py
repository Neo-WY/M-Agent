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

    prompt = agent._build_workspace_direct_judge_prompt(
        ws,
        ["EVID1"],
        prompt_key="workspace_direct_evidence_judge_prompt",
    )
    assert "useful_evidence_ids" in prompt
    assert "<original_question>" not in prompt

    out = llm_judge_direct(
        workspace=ws,
        new_evidence_ids=["EVID1"],
        ref_id_to_evidence_id={"E1": "EVID1"},
        llm_func=lambda _: '{"reason":"ok","status":"SUFFICIENT","useful_evidence_ids":["E1"],"next_query":null}',
        prompt_text="x",
    )
    assert out["status"] == "SUFFICIENT"
    assert out["next_query"] is None
    assert out["useful_evidence_ids"] == ["EVID1"]

    out2 = llm_judge_direct(
        workspace=ws,
        new_evidence_ids=["EVID1"],
        ref_id_to_evidence_id={"E1": "EVID1"},
        llm_func=lambda _: '{"reason":"need more","status":"INSUFFICIENT","useful_evidence_ids":["E1"],"next_query":"n"}',
        prompt_text="x",
    )
    assert out2["status"] == "INSUFFICIENT"
    assert out2["next_query"] == "n"

    print("direct_judge_smoke_ok")


if __name__ == "__main__":
    main()

