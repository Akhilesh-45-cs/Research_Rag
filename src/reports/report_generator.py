import os
import uuid
from datetime import datetime

from src.retrieval.retriever import retrieve_from_paper
from src.llm.groq_client import get_llm
from src.library.sessions import get_session, add_report_to_session
import markdown as md_lib
from xhtml2pdf import pisa

REPORTS_DIR = "data/reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

PAPER_SUMMARY_PROMPT = """Summarize this research paper's content in 3-5 sentences, 
covering: what problem it addresses, its method/approach, and its key results 
(include specific numbers if present). Be factual and concise.

Content:
{content}

Summary:"""

REPORT_SYNTHESIS_PROMPT = """You are writing a structured research report for someone 
studying the topic: "{topic}"

Below are summaries of {paper_count} papers on this topic. Write a well-organized 
report in Markdown with these sections:

## Introduction
Brief framing of the topic and why it matters (2-3 sentences).

## Papers Reviewed
A short table: Paper Title | Key Approach | Key Result

## Individual Summaries
One paragraph per paper, using its title as a subheading.

## Comparative Analysis
How do these papers' approaches and results compare? What patterns emerge?

## Research Gaps
Based on what these papers do and don't cover, what gaps or open questions exist? 
Be specific and grounded in what's actually present or absent in the summaries - 
don't invent gaps not supported by the content.

## Conclusion
2-3 sentence wrap-up.

Paper summaries:
{summaries}

Write the full report now:"""


def summarize_paper(paper_name):
    """Pulls key content (abstract/results/conclusion-leaning) from a paper and summarizes it."""
    results = retrieve_from_paper(
        "abstract introduction methodology results conclusion key findings",
        paper_name,
        top_k=6
    )
    chunks = results["documents"][0]

    if not chunks:
        return None

    content = "\n\n".join(chunks)
    llm = get_llm()
    prompt = PAPER_SUMMARY_PROMPT.format(content=content[:4000])  # cap length to control tokens
    response = llm.invoke(prompt)
    return response.content


def convert_markdown_to_pdf(markdown_text, output_path, title="Research Report"):
    """Converts markdown text to a styled PDF file. Returns True on success."""
    markdown_text = sanitize_for_pdf(markdown_text)
    html_body = md_lib.markdown(markdown_text, extensions=["tables"])

    html_content = f"""
    <html>
    <head>
    <style>
        body {{ font-family: Helvetica, Arial, sans-serif; font-size: 11pt; line-height: 1.5; color: #222; }}
        h1 {{ font-size: 20pt; border-bottom: 2px solid #C9A227; padding-bottom: 8px; }}
        h2 {{ font-size: 15pt; color: #4A7A8C; margin-top: 24px; }}
        h3 {{ font-size: 12.5pt; margin-top: 16px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
        th, td {{ border: 1px solid #999; padding: 6px 10px; text-align: left; font-size: 10pt; }}
        th {{ background-color: #f0f0f0; }}
        hr {{ border: none; border-top: 1px solid #ccc; margin: 16px 0; }}
    </style>
    </head>
    <body>
    {html_body}
    </body>
    </html>
    """

    with open(output_path, "wb") as f:
        pisa_status = pisa.CreatePDF(html_content, dest=f)

    return not pisa_status.err

def sanitize_for_pdf(text):
    """Replaces Unicode characters that xhtml2pdf's renderer handles poorly 
    with safe ASCII equivalents. Covers common dashes/hyphens/quotes the LLM 
    tends to output in compound words and punctuation."""
    replacements = {
        "\u2010": "-",   # hyphen
        "\u2011": "-",   # non-breaking hyphen (common in compound words like "real-time")
        "\u2012": "-",   # figure dash
        "\u2013": "-",   # en dash
        "\u2014": "-",   # em dash
        "\u2015": "-",   # horizontal bar
        "\u2018": "'",   # left single quote
        "\u2019": "'",   # right single quote
        "\u201a": "'",   # single low quote
        "\u201c": '"',   # left double quote
        "\u201d": '"',   # right double quote
        "\u201e": '"',   # double low quote
        "\u2212": "-",   # minus sign
        "\u00b2": "2",   # superscript 2 (R² -> R2)
        "\u00b3": "3",   # superscript 3
        "\u2192": "->",  # right arrow
        "\u2190": "<-",  # left arrow
        "\u2026": "...", # ellipsis
        "\u00a0": " ",   # non-breaking space
        "\u2022": "*",   # bullet
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)

    # Catch-all safety net: strip any remaining non-ASCII character that 
    # would otherwise render as a black box, rather than let one slip through
    text = text.encode("ascii", errors="ignore").decode("ascii")

    return text

def generate_report(session_id):
    """
    Generates a full structured report for a research session:
    1. Summarizes each paper in the session
    2. Synthesizes those summaries into one structured report
    3. Saves the report as both markdown and PDF
    4. Registers the PDF (or markdown, if PDF conversion fails) in the session's reports list
    Returns (report_id, filepath) or (None, error_message) on failure.
    """
    session = get_session(session_id)
    if session is None:
        return None, "Session not found"

    papers = session["papers"]
    if not papers:
        return None, "This session has no papers to report on"

    paper_summaries = []
    for paper_name in papers:
        summary = summarize_paper(paper_name)
        if summary:
            paper_summaries.append(f"### {paper_name}\n{summary}")

    if not paper_summaries:
        return None, "Could not extract content from any papers in this session"

    summaries_text = "\n\n".join(paper_summaries)

    llm = get_llm()
    synthesis_prompt = REPORT_SYNTHESIS_PROMPT.format(
        topic=session["topic_name"],
        paper_count=len(paper_summaries),
        summaries=summaries_text
    )
    response = llm.invoke(synthesis_prompt)
    report_content = response.content

    report_id = str(uuid.uuid4())
    safe_topic = session["topic_name"][:50].replace("/", "_").replace(" ", "_")
    md_filename = f"{safe_topic}_{report_id[:8]}.md"
    pdf_filename = f"{safe_topic}_{report_id[:8]}.pdf"
    md_filepath = os.path.join(REPORTS_DIR, md_filename)
    pdf_filepath = os.path.join(REPORTS_DIR, pdf_filename)

    header = f"# Research Report: {session['topic_name']}\n\n*Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} · {len(papers)} papers*\n\n---\n\n"
    full_markdown = header + report_content

    with open(md_filepath, "w", encoding="utf-8") as f:
        f.write(full_markdown)

    pdf_success = convert_markdown_to_pdf(full_markdown, pdf_filepath, title=session["topic_name"])

    report_title = f"Report: {session['topic_name']}"
    final_path = pdf_filepath if pdf_success else md_filepath
    add_report_to_session(session_id, report_title, final_path)

    return report_id, final_path


if __name__ == "__main__":
    from src.library.sessions import get_all_sessions_sorted

    sessions = get_all_sessions_sorted()
    if not sessions:
        print("No sessions found. Create one first (upload/fetch a paper).")
    else:
        test_session = sessions[0]
        print(f"Generating report for: {test_session['topic_name']}")
        report_id, filepath = generate_report(test_session["session_id"])
        if report_id:
            print(f"Report saved: {filepath}")
        else:
            print(f"Failed: {filepath}")