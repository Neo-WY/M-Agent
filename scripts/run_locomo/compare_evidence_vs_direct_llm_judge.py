import json
from pathlib import Path


def load_scores(path: Path) -> dict[tuple[str, int, str], float]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[tuple[str, int, str], float] = {}
    for sample in data:
        sid = str(sample.get("sample_id"))
        for i, qa in enumerate(sample.get("qa", [])):
            score = qa.get("memory_agent_llm_judge_score")
            if score is None:
                continue
            if int(qa.get("category", -1)) == 5:
                continue
            key = (sid, int(qa.get("qa_index", i)), str(qa.get("question", "")))
            out[key] = float(score)
    return out


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True, help="Path to evidence locomo10_agent_qa.json")
    ap.add_argument("--direct", required=True, help="Path to direct locomo10_agent_qa.json")
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args()

    ev_path = Path(args.evidence)
    dr_path = Path(args.direct)
    ev = load_scores(ev_path)
    dr = load_scores(dr_path)
    keys = set(ev).intersection(dr)

    rows: list[tuple[float, float, float, tuple[str, int, str]]] = []
    for k in keys:
        de = ev[k]
        dd = dr[k]
        rows.append((dd - de, de, dd, k))
    rows.sort()

    print("common", len(keys), "ev_only", len(set(ev) - keys), "dr_only", len(set(dr) - keys))
    print()
    print("worst direct relative (direct - evidence):")
    for d, de, dd, k in rows[: args.top]:
        q = k[2][:100].replace("\n", " ")
        print(f"{d:+.3f}  ev={de:.3f} dr={dd:.3f}  qa_index={k[1]}  q={q}")
    print()
    print("best direct relative (direct - evidence):")
    for d, de, dd, k in rows[-args.top :][::-1]:
        q = k[2][:100].replace("\n", " ")
        print(f"{d:+.3f}  ev={de:.3f} dr={dd:.3f}  qa_index={k[1]}  q={q}")


if __name__ == "__main__":
    main()

