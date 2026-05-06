from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import markdown


def resolve_edge_path() -> Path:
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("No Edge/Chrome executable found in standard install paths.")


def render_html(md_text: str, title: str) -> str:
    body = markdown.markdown(md_text, extensions=["extra", "sane_lists", "nl2br"])
    css = (
        "<style>"
        "body{font-family:Microsoft YaHei,Segoe UI,Arial,sans-serif;line-height:1.65;max-width:980px;"
        "margin:28px auto;padding:0 20px;color:#111}"
        "h1,h2,h3{line-height:1.3}"
        "code{background:#f5f5f5;padding:2px 4px;border-radius:4px}"
        "pre{background:#f8f8f8;padding:12px;border-radius:8px;overflow:auto}"
        "ul,ol{padding-left:1.4em}"
        "hr{border:none;border-top:1px solid #ddd;margin:24px 0}"
        "@media print{body{max-width:none;margin:10mm}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}}"
        "</style>"
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{title}</title>{css}</head><body>{body}</body></html>"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert Markdown to PDF via Edge/Chrome headless print.")
    parser.add_argument("markdown_file", type=str, help="Path to source markdown file.")
    parser.add_argument("--pdf-out", type=str, default="", help="Optional output pdf path.")
    parser.add_argument("--html-out", type=str, default="", help="Optional output html path.")
    args = parser.parse_args()

    md_path = Path(args.markdown_file).resolve()
    if not md_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    pdf_path = Path(args.pdf_out).resolve() if args.pdf_out else md_path.with_suffix(".pdf")
    html_path = Path(args.html_out).resolve() if args.html_out else md_path.with_suffix(".html")

    text = md_path.read_text(encoding="utf-8")
    html_path.write_text(render_html(text, md_path.stem), encoding="utf-8")

    browser = resolve_edge_path()
    file_url = html_path.as_uri()
    cmd = [
        str(browser),
        "--headless=new",
        "--disable-gpu",
        "--allow-file-access-from-files",
        f"--print-to-pdf={pdf_path}",
        file_url,
    ]
    subprocess.run(cmd, check=True)
    print(f"HTML: {html_path}")
    print(f"PDF: {pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
