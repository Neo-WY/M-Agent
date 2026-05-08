import json
from pathlib import Path


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--qa", required=True, help="Path to locomo10_agent_qa.json")
    ap.add_argument("--idx", nargs="+", required=True, help="qa_index values to print")
    ap.add_argument("--max-chars", type=int, default=260)
    args = ap.parse_args()

    idxs = {int(x) for x in args.idx}
    path = Path(args.qa)
    data = json.loads(path.read_text(encoding="utf-8"))
    # locomo runs are typically single-sample per file (conv-xx), but handle multiple.
    items = []
    for sample in data:
        sid = str(sample.get("sample_id"))
        for i, qa in enumerate(sample.get("qa", [])):
            # Some legacy logs may not store qa_index; fall back to list index.
            qidx = int(qa.get("qa_index", i))
            if qidx in idxs:
                items.append((sid, qidx, qa))

    items.sort(key=lambda t: (t[0], t[1]))
    for sid, qidx, qa in items:
        judge = qa.get("memory_agent_llm_judge") or {}
        print("=" * 80)
        print("sample_id:", sid, "qa_index:", qidx, "category:", qa.get("category"))
        print(
            "llm_judge_score:",
            qa.get("memory_agent_llm_judge_score"),
            "label:",
            judge.get("label"),
            "correct_count:",
            judge.get("correct_count"),
            "num_runs:",
            judge.get("num_runs"),
        )
        print("Q:", qa.get("question"))
        print("gold:", str(qa.get("answer"))[: args.max_chars])
        pred = str(qa.get("memory_agent_prediction_answer", "") or "")
        print("pred_answer_snip:", pred[: args.max_chars].replace("\n", " "))
        print("evidence_ids:", qa.get("evidence"))


if __name__ == "__main__":
    main()

