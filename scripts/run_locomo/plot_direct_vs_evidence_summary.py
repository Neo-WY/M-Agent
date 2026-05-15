from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch


ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / "log"
OUT_DIR = ROOT / "artifacts" / "locomo"

CONVS = ["26", "30", "41", "42", "43", "44", "47", "48", "49", "50"]

CATEGORY_LABELS = {
    "1": "Multi-Hop",
    "2": "Temporal",
    "3": "Commonsense",
    "4": "Single-Hop",
    "5": "Adversarial",
}

STANDARD_EVIDENCE_DIRS = {
    "26": "new_baseline__conv-26_new-blip__conv-26",
    "30": "new_baseline__conv-30-new-blip__conv-30",
    "41": "new_baseline__conv-41-new-blip__conv-41",
    "42": "new_baseline__conv-42-new-blip__conv-42",
    "43": "new_baseline__conv-43-new-blip__conv-43",
    "44": "new_baseline__conv-44-new-blip__conv-44",
    "47": "new_baseline__conv-47-new-blip__conv-47",
    "48": "new_baseline__conv-48-new-blip__conv-48",
    "49": "new_baseline__conv-49-new-blip__conv-49",
    "50": "new_baseline__conv-50-new-blip__conv-50",
}

STANDARD_DIRECT_DIRS = {c: f"new_baseline__conv-{c}-direct-blip" for c in CONVS}
ADVERSARIAL_EVIDENCE_DIRS = {c: f"new_baseline__conv-{c}-blip-adversarial" for c in CONVS}
ADVERSARIAL_DIRECT_DIRS = {c: f"new_baseline__conv-{c}-direct-blip-adversarial" for c in CONVS}


def load_stats(dir_name: str) -> dict:
    path = LOG_DIR / dir_name / "locomo10_agent_qa_stats.json"
    return json.loads(path.read_text(encoding="utf-8"))


def weighted_standard(dir_map: dict[str, str]) -> dict:
    totals = {"acc": 0.0, "b1": 0.0, "recall": 0.0, "exec": 0.0, "llm": 0.0}
    total = 0
    total_llm = 0
    cat_acc = {str(i): {"num": 0.0, "den": 0} for i in range(1, 5)}
    cat_llm = {str(i): {"num": 0.0, "den": 0} for i in range(1, 5)}

    for conv in CONVS:
        data = load_stats(dir_map[conv])
        metric = data["memory_agent"]
        count = sum(metric["category_counts"].get(str(i), 0) for i in range(1, 5))
        total += count
        totals["acc"] += metric["overall_accuracy"] * count
        totals["b1"] += metric["overall_b1"] * count
        totals["recall"] += metric["overall_recall"] * count
        totals["exec"] += metric["overall_workspace_execute_recall"] * count

        for i in range(1, 5):
            key = str(i)
            block = metric["summary_by_category"][key]
            cat_acc[key]["den"] += block["count"]
            cat_acc[key]["num"] += block["accuracy"] * block["count"]

        judge = data["memory_agent_llm_judge"]
        judge_count = sum(judge["category_counts"].get(str(i), 0) for i in range(1, 5))
        total_llm += judge_count
        totals["llm"] += judge["overall_accuracy"] * judge_count

        for i in range(1, 5):
            key = str(i)
            block = judge["summary_by_category"][key]
            cat_llm[key]["den"] += block["count"]
            cat_llm[key]["num"] += block["accuracy"] * block["count"]

    return {
        "overall": {k: totals[k] / (total_llm if k == "llm" else total) for k in totals},
        "cat_acc": {k: cat_acc[k]["num"] / cat_acc[k]["den"] for k in cat_acc},
        "cat_llm": {k: cat_llm[k]["num"] / cat_llm[k]["den"] for k in cat_llm},
        "total": total,
        "total_llm": total_llm,
    }


def weighted_adversarial(dir_map: dict[str, str]) -> dict:
    total = 0
    score = 0.0
    per_conv = []
    for conv in CONVS:
        judge = load_stats(dir_map[conv])["memory_agent_llm_judge"]
        block = judge["summary_by_category"]["5"]
        total += block["count"]
        score += judge["overall_accuracy"] * block["count"]
        per_conv.append(
            {
                "conv": f"conv-{conv}",
                "count": block["count"],
                "score": judge["overall_accuracy"],
            }
        )
    return {"overall": score / total, "total": total, "per_conv": per_conv}


def add_card(fig: plt.Figure, x: float, y: float, w: float, h: float, title: str, left: str, right: str) -> None:
    shadow = FancyBboxPatch(
        (x + 0.004, y - 0.004),
        w,
        h,
        boxstyle="round,pad=0.008,rounding_size=0.018",
        linewidth=0,
        facecolor=(0, 0, 0, 0.22),
        transform=fig.transFigure,
        zorder=1,
    )
    fig.patches.append(shadow)
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.008,rounding_size=0.018",
        linewidth=1.2,
        edgecolor="#27435f",
        facecolor="#0f1f32",
        transform=fig.transFigure,
        zorder=2,
    )
    fig.patches.append(patch)
    fig.text(x + 0.015, y + h - 0.03, title, color="#8fb6d9", fontsize=11, fontweight="bold", zorder=3)
    fig.text(x + 0.015, y + 0.03, left, color="#7ce2c6", fontsize=18, fontweight="bold", zorder=3)
    fig.text(x + w - 0.015, y + 0.03, right, color="#ffbf70", fontsize=18, ha="right", fontweight="bold", zorder=3)


def style_axis(ax: plt.Axes, title: str) -> None:
    ax.set_facecolor("#0c1728")
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="x", color="#27435f", alpha=0.35, linewidth=0.8)
    ax.tick_params(colors="#d7e6f5", labelsize=11)
    ax.set_title(title, color="white", fontsize=16, fontweight="bold", pad=14)
    ax.set_axisbelow(True)


def plot_grouped_bars(ax: plt.Axes, labels: list[str], left_vals: list[float], right_vals: list[float], left_name: str, right_name: str) -> None:
    x = np.arange(len(labels))
    width = 0.34
    bars1 = ax.bar(x - width / 2, left_vals, width, color="#27d7a1", label=left_name, alpha=0.95)
    bars2 = ax.bar(x + width / 2, right_vals, width, color="#ff9b54", label=right_name, alpha=0.95)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 1.0)
    ax.legend(frameon=False, loc="upper left", fontsize=11, labelcolor="white")
    for bars in (bars1, bars2):
        for bar in bars:
            h = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h + 0.018,
                f"{h:.3f}",
                ha="center",
                va="bottom",
                color="white",
                fontsize=10,
                fontweight="bold",
            )


def build_figure(summary: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(17, 10), facecolor="#07111f")
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.08], hspace=0.30, wspace=0.18)

    fig.text(
        0.05,
        0.965,
        "LoCoMo: Evidence-State Control vs LLM-Driven Direct Control",
        color="white",
        fontsize=24,
        fontweight="bold",
    )
    fig.text(
        0.05,
        0.935,
        "Weighted across conv-26/30/41/42/43/44/47/48/49/50. Standard QA uses categories 1-4; adversarial uses category 5 only.",
        color="#9ab6d0",
        fontsize=12,
    )

    se = summary["standard_evidence"]["overall"]
    sd = summary["standard_direct"]["overall"]
    ae = summary["adversarial_evidence"]["overall"]
    ad = summary["adversarial_direct"]["overall"]

    add_card(fig, 0.05, 0.84, 0.18, 0.075, "Overall Accuracy", f"{se['acc']:.3f}", f"{sd['acc']:.3f}")
    add_card(fig, 0.245, 0.84, 0.18, 0.075, "Overall B1", f"{se['b1']:.3f}", f"{sd['b1']:.3f}")
    add_card(fig, 0.44, 0.84, 0.18, 0.075, "Overall Recall", f"{se['recall']:.3f}", f"{sd['recall']:.3f}")
    add_card(fig, 0.635, 0.84, 0.18, 0.075, "Workspace Exec Recall", f"{se['exec']:.3f}", f"{sd['exec']:.3f}")
    add_card(fig, 0.83, 0.84, 0.12, 0.075, "Cat5 Adv.", f"{ae:.3f}", f"{ad:.3f}")

    labels = [CATEGORY_LABELS[str(i)] for i in range(1, 5)]
    e_acc = [summary["standard_evidence"]["cat_acc"][str(i)] for i in range(1, 5)]
    d_acc = [summary["standard_direct"]["cat_acc"][str(i)] for i in range(1, 5)]
    e_llm = [summary["standard_evidence"]["cat_llm"][str(i)] for i in range(1, 5)]
    d_llm = [summary["standard_direct"]["cat_llm"][str(i)] for i in range(1, 5)]

    ax1 = fig.add_subplot(gs[0, 0])
    style_axis(ax1, "Standard QA Accuracy by Category")
    plot_grouped_bars(ax1, labels, e_acc, d_acc, "Evidence", "Direct")
    ax1.set_ylabel("Weighted Accuracy", color="#d7e6f5", fontsize=12)

    ax2 = fig.add_subplot(gs[0, 1])
    style_axis(ax2, "Standard QA LLM-Judge by Category")
    plot_grouped_bars(ax2, labels, e_llm, d_llm, "Evidence", "Direct")
    ax2.set_ylabel("Weighted LLM-Judge Accuracy", color="#d7e6f5", fontsize=12)

    ax3 = fig.add_subplot(gs[1, :])
    style_axis(ax3, "Adversarial Category-5 Success Rate")
    conv_labels = [item["conv"] for item in summary["adversarial_evidence"]["per_conv"]]
    ev = [item["score"] for item in summary["adversarial_evidence"]["per_conv"]]
    dv = [item["score"] for item in summary["adversarial_direct"]["per_conv"]]
    x = np.arange(len(conv_labels))
    width = 0.34
    bars1 = ax3.bar(x - width / 2, ev, width, color="#27d7a1", alpha=0.95, label="Evidence")
    bars2 = ax3.bar(x + width / 2, dv, width, color="#ff9b54", alpha=0.95, label="Direct")
    ax3.set_xticks(x, conv_labels)
    ax3.set_ylim(0, 1.0)
    ax3.legend(frameon=False, loc="upper right", fontsize=12, labelcolor="white")
    ax3.set_ylabel("Adversarial Success", color="#d7e6f5", fontsize=12)

    for b in list(bars1) + list(bars2):
        h = b.get_height()
        ax3.text(
            b.get_x() + b.get_width() / 2,
            h + 0.014,
            f"{h:.2f}",
            ha="center",
            va="bottom",
            color="white",
            fontsize=9,
            fontweight="bold",
            rotation=90,
        )

    delta = ae - ad
    ax3.text(
        0.015,
        0.95,
        f"Weighted Cat5 gap: +{delta:.3f} for Evidence ({ae:.3f} vs {ad:.3f})",
        transform=ax3.transAxes,
        color="#ffffff",
        fontsize=18,
        fontweight="bold",
        va="top",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#11253b", edgecolor="#2f4f6d", alpha=0.95),
    )

    fig.text(0.05, 0.03, "Colors: Evidence-state control", color="#27d7a1", fontsize=11, fontweight="bold")
    fig.text(0.25, 0.03, "Direct LLM-driven control", color="#ff9b54", fontsize=11, fontweight="bold")

    out_png = OUT_DIR / "direct_vs_evidence_summary.png"
    out_pdf = OUT_DIR / "direct_vs_evidence_summary.pdf"
    fig.savefig(out_png, dpi=220, facecolor=fig.get_facecolor(), bbox_inches="tight")
    fig.savefig(out_pdf, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return out_png


def build_radar(summary: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    categories = [
        CATEGORY_LABELS["1"],
        CATEGORY_LABELS["2"],
        CATEGORY_LABELS["3"],
        CATEGORY_LABELS["4"],
        CATEGORY_LABELS["5"],
    ]
    evidence_vals = [
        summary["standard_evidence"]["cat_llm"]["1"],
        summary["standard_evidence"]["cat_llm"]["2"],
        summary["standard_evidence"]["cat_llm"]["3"],
        summary["standard_evidence"]["cat_llm"]["4"],
        summary["adversarial_evidence"]["overall"],
    ]
    direct_vals = [
        summary["standard_direct"]["cat_llm"]["1"],
        summary["standard_direct"]["cat_llm"]["2"],
        summary["standard_direct"]["cat_llm"]["3"],
        summary["standard_direct"]["cat_llm"]["4"],
        summary["adversarial_direct"]["overall"],
    ]

    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    angles += angles[:1]
    evidence_vals += evidence_vals[:1]
    direct_vals += direct_vals[:1]

    fig = plt.figure(figsize=(11, 10), facecolor="#07111f")
    ax = plt.subplot(111, polar=True)
    ax.set_facecolor("#0b1627")
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, color="white", fontsize=13, fontweight="bold")
    ax.set_ylim(0, 1.0)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], color="#8fb6d9", fontsize=11)
    ax.yaxis.grid(True, color="#335777", alpha=0.45, linewidth=1.0)
    ax.xaxis.grid(True, color="#335777", alpha=0.30, linewidth=1.0)
    ax.spines["polar"].set_color("#335777")
    ax.spines["polar"].set_linewidth(1.2)

    ax.plot(angles, evidence_vals, color="#27d7a1", linewidth=3.2, label="Evidence-State Control")
    ax.fill(angles, evidence_vals, color="#27d7a1", alpha=0.22)
    ax.scatter(angles[:-1], evidence_vals[:-1], color="#8af5d7", s=55, zorder=5)

    ax.plot(angles, direct_vals, color="#ff9b54", linewidth=3.2, label="Direct LLM-Driven Control")
    ax.fill(angles, direct_vals, color="#ff9b54", alpha=0.18)
    ax.scatter(angles[:-1], direct_vals[:-1], color="#ffd1ab", s=55, zorder=5)

    for angle, val in zip(angles[:-1], evidence_vals[:-1]):
        ax.text(angle, min(val + 0.06, 1.04), f"{val:.3f}", color="#b9fff0", fontsize=10, ha="center", va="center")
    for angle, val in zip(angles[:-1], direct_vals[:-1]):
        ax.text(angle, max(val - 0.08, 0.05), f"{val:.3f}", color="#ffe0c6", fontsize=10, ha="center", va="center")

    fig.text(
        0.08,
        0.95,
        "Category-Wise Five-Dimensional Radar",
        color="white",
        fontsize=24,
        fontweight="bold",
    )
    fig.text(
        0.08,
        0.92,
        "Multi-Hop / Temporal / Commonsense / Single-Hop use weighted LLM-judge accuracy; Adversarial uses adversarial success rate.",
        color="#9ab6d0",
        fontsize=12,
    )
    fig.text(
        0.08,
        0.08,
        (
            f"Adversarial gap is the dominant visual signal: "
            f"{summary['adversarial_evidence']['overall']:.3f} vs {summary['adversarial_direct']['overall']:.3f}"
        ),
        color="#ffffff",
        fontsize=14,
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.45", facecolor="#11253b", edgecolor="#2f4f6d", alpha=0.95),
    )

    ax.legend(loc="upper right", bbox_to_anchor=(1.28, 1.14), frameon=False, fontsize=12, labelcolor="white")

    out_png = OUT_DIR / "direct_vs_evidence_radar.png"
    out_pdf = OUT_DIR / "direct_vs_evidence_radar.pdf"
    fig.savefig(out_png, dpi=220, facecolor=fig.get_facecolor(), bbox_inches="tight")
    fig.savefig(out_pdf, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return out_png


def build_paper_radar(summary: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    categories = [
        CATEGORY_LABELS["1"],
        CATEGORY_LABELS["2"],
        CATEGORY_LABELS["3"],
        CATEGORY_LABELS["4"],
        CATEGORY_LABELS["5"],
    ]
    evidence_vals = [
        summary["standard_evidence"]["cat_llm"]["1"],
        summary["standard_evidence"]["cat_llm"]["2"],
        summary["standard_evidence"]["cat_llm"]["3"],
        summary["standard_evidence"]["cat_llm"]["4"],
        summary["adversarial_evidence"]["overall"],
    ]
    direct_vals = [
        summary["standard_direct"]["cat_llm"]["1"],
        summary["standard_direct"]["cat_llm"]["2"],
        summary["standard_direct"]["cat_llm"]["3"],
        summary["standard_direct"]["cat_llm"]["4"],
        summary["adversarial_direct"]["overall"],
    ]

    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    angles += angles[:1]
    evidence_vals += evidence_vals[:1]
    direct_vals += direct_vals[:1]

    plt.rcParams.update(
        {
            "font.family": "DejaVu Serif",
            "axes.edgecolor": "#8c96a3",
            "axes.linewidth": 0.8,
        }
    )

    fig = plt.figure(figsize=(8.4, 6.8), facecolor="white")
    ax = plt.subplot(111, polar=True)
    ax.set_facecolor("white")
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=12)
    ax.set_ylim(0, 1.0)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], fontsize=10, color="#5d6875")
    ax.yaxis.grid(True, color="#d5dbe3", linewidth=0.9)
    ax.xaxis.grid(True, color="#e5e9ef", linewidth=0.9)
    ax.spines["polar"].set_color("#9aa4b2")
    ax.spines["polar"].set_linewidth(0.9)

    evidence_line = "#0f8b8d"
    direct_line = "#d66a2c"
    evidence_fill = "#7bd3d4"
    direct_fill = "#f2b38a"

    ax.plot(angles, evidence_vals, color=evidence_line, linewidth=2.6, label="Evidence-State Control")
    ax.fill(angles, evidence_vals, color=evidence_fill, alpha=0.35)
    ax.scatter(angles[:-1], evidence_vals[:-1], color=evidence_line, s=28, zorder=4)

    ax.plot(angles, direct_vals, color=direct_line, linewidth=2.6, label="Direct LLM-Driven Control")
    ax.fill(angles, direct_vals, color=direct_fill, alpha=0.25)
    ax.scatter(angles[:-1], direct_vals[:-1], color=direct_line, s=28, zorder=4)

    for angle, val in zip(angles[:-1], evidence_vals[:-1]):
        ax.text(angle, min(val + 0.045, 1.02), f"{val:.3f}", color=evidence_line, fontsize=9, ha="center", va="center")
    for angle, val in zip(angles[:-1], direct_vals[:-1]):
        ax.text(angle, max(val - 0.055, 0.04), f"{val:.3f}", color=direct_line, fontsize=9, ha="center", va="center")

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.04),
        ncol=2,
        frameon=False,
        fontsize=11,
        handlelength=2.8,
    )

    out_png = OUT_DIR / "direct_vs_evidence_radar_paper.png"
    out_pdf = OUT_DIR / "direct_vs_evidence_radar_paper.pdf"
    fig.savefig(out_png, dpi=300, facecolor="white", bbox_inches="tight")
    fig.savefig(out_pdf, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return out_png


def main() -> None:
    summary = {
        "standard_evidence": weighted_standard(STANDARD_EVIDENCE_DIRS),
        "standard_direct": weighted_standard(STANDARD_DIRECT_DIRS),
        "adversarial_evidence": weighted_adversarial(ADVERSARIAL_EVIDENCE_DIRS),
        "adversarial_direct": weighted_adversarial(ADVERSARIAL_DIRECT_DIRS),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = OUT_DIR / "direct_vs_evidence_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    image_path = build_figure(summary)
    radar_path = build_radar(summary)
    paper_radar_path = build_paper_radar(summary)
    print(f"Saved summary json: {summary_path}")
    print(f"Saved figure: {image_path}")
    print(f"Saved radar: {radar_path}")
    print(f"Saved paper radar: {paper_radar_path}")


if __name__ == "__main__":
    main()
