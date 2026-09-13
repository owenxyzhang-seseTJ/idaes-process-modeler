#!/usr/bin/env python3
"""Render Markdown reports to PDF and page previews with XeLaTeX."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
PDF_ROOT = ROOT / "output" / "pdf" / "reports"
PREVIEW_ROOT = ROOT / "output" / "preview" / "reports"
CONTACT_SHEET = ROOT / "output" / "preview" / "report_contact_sheet.png"
TMP_ROOT = ROOT / "tmp" / "pdfs"

REPORTS = (
    ("demo_technical_report", "demo_results/technical_report/demo_technical_report.md"),
    ("gate_open_thermal_psa_report", "demo_results/gate_open_thermal_psa/report.md"),
    ("technical_report_figure_plan", "demo_results/technical_report/figure_plan.md"),
    ("technical_report_method_search_packet", "demo_results/technical_report/method_search_packet.md"),
    ("technical_report_qa_report", "demo_results/technical_report/qa_report.md"),
    ("gate_open_thermal_psa_figure_plan", "demo_results/gate_open_thermal_psa/figure_plan.md"),
    (
        "gate_open_thermal_psa_method_search_packet",
        "demo_results/gate_open_thermal_psa/method_search_packet.md",
    ),
    ("gate_open_thermal_psa_qa_report", "demo_results/gate_open_thermal_psa/qa_report.md"),
)


def latex_wrapper(source_name: str) -> str:
    """Return a temporary XeLaTeX wrapper whose working directory is the report directory."""

    return rf"""\documentclass[UTF8,11pt]{{ctexart}}
\usepackage[a4paper,margin=18mm]{{geometry}}
\usepackage{{amsmath,amssymb}}
\usepackage{{graphicx}}
\usepackage{{booktabs,longtable,array}}
\usepackage{{adjustbox}}
\usepackage{{xcolor}}
\usepackage{{hyperref}}
\usepackage{{bookmark}}
\usepackage[
  contentBlocks,
  fencedCode,
  pipeTables,
  rawAttribute,
  texMathDollars,
  texMathDoubleBackslash,
  texMathSingleBackslash,
]{{markdown}}
\setmainfont{{Arial Unicode MS}}
\setcounter{{secnumdepth}}{{0}}
\setlength{{\parindent}}{{0pt}}
\setlength{{\parskip}}{{0.45em}}
\setlength{{\emergencystretch}}{{3em}}
\hypersetup{{hidelinks}}
\sloppy
\makeatletter
\def\markdownLaTeXRenderTableRow#1{{%
  \markdownLaTeXColumnCounter=0%
  \ifnum\markdownLaTeXRowCounter=0\relax
    \markdownLaTeXReadAlignments#1%
    \markdownLaTeXTable=\expandafter\expandafter\expandafter{{%
      \expandafter\the\expandafter\markdownLaTeXTable\expandafter{{%
        \the\markdownLaTeXTableAlignment}}}}
    \addto@hook\markdownLaTeXTable{{\markdownLaTeXTopRule}}%
  \else
    \markdownLaTeXRenderTableCell#1%
  \fi
  \ifnum\markdownLaTeXRowCounter=1\relax
    \addto@hook\markdownLaTeXTable\markdownLaTeXMidRule
  \fi
  \advance\markdownLaTeXRowCounter by 1\relax
  \ifnum\markdownLaTeXRowCounter>\markdownLaTeXRowTotal\relax
    \begin{{adjustbox}}{{max width=\linewidth}}% # figure-comment-exempt: LaTeX 表格钩子，控制表格最大宽度
    \the\markdownLaTeXTable
    \the\markdownLaTeXTableEnd
    \end{{adjustbox}}%
    \expandafter\@gobble
  \fi\markdownLaTeXRenderTableRow}}
\makeatother
% Keep report images inside the page while preserving their aspect ratio.
\markdownSetup{{
  rendererPrototypes = {{
    image = {{\begin{{center}}\includegraphics[width=\linewidth,height=0.72\textheight,keepaspectratio]{{#3}}\end{{center}}}}, % 图片按页面宽高约束并保持比例
  }},
}}
\begin{{document}}
\markdownInput{{{source_name}}}
\end{{document}}
"""


def run_command(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a command and return captured output for auditable failures."""

    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)


def render_one(stem: str, source_rel: str) -> dict:
    """Compile one Markdown source, render its pages, and return relative metadata."""

    source = ROOT / source_rel
    if not source.is_file():
        raise FileNotFoundError(f"Missing report source: {source_rel}")
    pdf_path = PDF_ROOT / f"{stem}.pdf"
    preview_dir = PREVIEW_ROOT / stem
    build_dir = TMP_ROOT / stem
    preview_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)
    for stale_page in preview_dir.glob("page-*.png"):
        stale_page.unlink()
    wrapper = source.parent / f"codex-render-{stem}.tex"
    wrapper.write_text(latex_wrapper(source.name), encoding="utf-8")
    try:
        command = [
            "xelatex",
            "-shell-escape",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            "-output-directory",
            str(build_dir),
            wrapper.name,
        ]
        first = run_command(command, source.parent)
        second = run_command(command, source.parent)
        if first.returncode != 0 or second.returncode != 0:
            details = (second.stdout + "\n" + second.stderr)[-12000:]
            raise RuntimeError(f"XeLaTeX failed for {source_rel}:\n{details}")
        built_pdf = build_dir / f"{wrapper.stem}.pdf"
        if not built_pdf.is_file():
            raise RuntimeError(f"XeLaTeX did not create a PDF for {source_rel}")
        PDF_ROOT.mkdir(parents=True, exist_ok=True)
        shutil.copy2(built_pdf, pdf_path)
    finally:
        wrapper.unlink(missing_ok=True)

    prefix = preview_dir / "page"
    preview_command = ["pdftoppm", "-png", "-r", "144", str(pdf_path), str(prefix)]
    preview_result = run_command(preview_command, ROOT)
    if preview_result.returncode != 0:
        raise RuntimeError(
            f"pdftoppm failed for {source_rel}:\n{preview_result.stdout}\n{preview_result.stderr}"
        )
    page_paths = sorted(preview_dir.glob("page-*.png"))
    if not page_paths:
        raise RuntimeError(f"No rendered pages found for {source_rel}")

    reader = PdfReader(str(pdf_path))
    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    if len(extracted_text.strip()) < 80:
        raise RuntimeError(f"PDF text extraction is unexpectedly short for {source_rel}")
    return {
        "source": source_rel,
        "pdf": str(pdf_path.relative_to(ROOT)),
        "preview_dir": str(preview_dir.relative_to(ROOT)),
        "pages": len(page_paths),
        "text_characters": len(extracted_text),
        "pdf_bytes": pdf_path.stat().st_size,
        "page_files": [str(path.relative_to(ROOT)) for path in page_paths],
    }


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a stable contact-sheet font, falling back to Pillow's bundled font."""  # 选择稳定的联系页字体并提供内置字体回退

    candidates = (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def build_contact_sheet(records: list[dict]) -> None:
    """Create a compact visual index containing every rendered report page."""

    cards: list[tuple[str, Path]] = []
    for record in records:
        stem = Path(record["pdf"]).stem
        for page_path in record["page_files"]:
            cards.append((f"{stem} | {Path(page_path).stem}", ROOT / page_path))
    columns = 3
    card_width = 430
    card_height = 330
    rows = (len(cards) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * card_width, rows * card_height), "#F4F6F7")  # 设定联系页背景，便于快速发现页面边界和空白异常
    draw = ImageDraw.Draw(sheet)
    label_font = load_font(17)
    for index, (label, page_path) in enumerate(cards):
        with Image.open(page_path) as page_image:
            thumb = ImageOps.contain(page_image.convert("RGB"), (card_width - 28, card_height - 58))  # 将每页等比例缩略到卡片内，避免拉伸公式和图像
        x = (index % columns) * card_width
        y = (index // columns) * card_height
        draw.rectangle((x + 8, y + 8, x + card_width - 8, y + card_height - 8), fill="white", outline="#CBD5D8", width=2)  # 绘制白色页面卡片和浅色边框
        image_x = x + (card_width - thumb.width) // 2  # 计算缩略图水平居中位置，保持每页左右留白一致
        image_y = y + 18
        sheet.paste(thumb, (image_x, image_y))  # 把逐页预览放入联系页，保留原始页面比例
        draw.text((x + 16, y + card_height - 34), label, fill="#27323A", font=label_font)  # 标注报告名称和页码，方便定位需要放大的页面
    CONTACT_SHEET.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(CONTACT_SHEET, format="PNG", dpi=(144, 144))  # 导出联系页 PNG，供 README 和应用内预览直接使用


def main() -> None:
    """Render all maintained reports and write a path-portable manifest."""

    PDF_ROOT.mkdir(parents=True, exist_ok=True)
    PREVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    if TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    try:
        for stem, source_rel in REPORTS:
            records.append(render_one(stem, source_rel))
        build_contact_sheet(records)
    finally:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)
    manifest = {
        "renderer": "XeLaTeX + markdown.sty + ctexart",
        "page_renderer": "pdftoppm",
        "reports": records,
        "contact_sheet": str(CONTACT_SHEET.relative_to(ROOT)),
    }
    manifest_path = PREVIEW_ROOT.parent / "report_render_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
