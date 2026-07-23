import json
from src.llm.groq_client import get_llm
from src.llm.groq_client import get_fast_llm

ROUTER_PROMPT = """You are the routing brain for a research paper assistant.
Given the conversation history, the list of available papers, and the user's new message,
decide how to handle it. Respond with ONLY a JSON object, no other text, no markdown.

Available papers:
{paper_list}

Conversation history (most recent last, USER and ASSISTANT turns):
{history}

New user message: {question}

Determine:
1. "category": one of "greeting", "irrelevant", "single_paper", "comparison", "general", "library_meta", "recent_papers"
   - "greeting": hi/hello/thanks, no real question
   - "irrelevant": real question but unrelated to research papers
   - "single_paper": question is about the CONTENT of ONE specific paper
   - "comparison": question asks to compare/rank/find best across MULTIPLE specific named 
     papers, or explicitly "all" papers
   - "general": a research question not tied to one specific paper
   - "library_meta": question asks about which papers exist, are uploaded, or available - 
     NOT about paper content (e.g. "is X paper here", "what papers do I have", "list my papers")
    - "recent_papers": question specifically asks about the LATEST, MOST RECENT, or NEWLY ADDED 
     papers (e.g. "latest 3 papers", "papers I just added", "recently uploaded papers") - NOT 
     about paper content in general

2. "target_papers": a list of EXACT paper names copied from the available papers list above 
   that this question concerns. Empty list if none apply, or if category is "comparison" and 
   means literally all papers.

3. "standalone_question": rewrite the user's new message into a fully self-contained question. 
   Resolve references ONLY using what the USER previously asked or named - never invent or 
   reuse a paper name just because the ASSISTANT mentioned it in a past answer.

4. "recent_count": if category is "recent_papers", the number of papers requested (default 3 if not specified). Otherwise 0.

Respond with ONLY valid JSON:
{{"category": "...", "target_papers": [...], "standalone_question": "...", "recent_count": 0}}
"""


def route_query(question, chat_history, paper_names, max_history_turns=6):
    recent = chat_history[-max_history_turns:] if chat_history else []
    history_text = "\n".join(
        f"{turn['role'].upper()}: {turn['content'][:300]}" for turn in recent
    ) or "(no previous messages)"
    paper_list_text = "\n".join(f"- {name}" for name in paper_names) or "(no papers uploaded yet)"

    llm = get_fast_llm()
    prompt = ROUTER_PROMPT.format(paper_list=paper_list_text, history=history_text, question=question)
    response = llm.invoke(prompt)

    raw = response.content.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"category": "general", "target_papers": [], "standalone_question": question}

    return parsed