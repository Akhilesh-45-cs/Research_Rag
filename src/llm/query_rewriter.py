from src.llm.groq_client import get_llm

REWRITE_PROMPT = """Given the recent conversation history and a new question, rewrite the 
new question into a standalone question that includes any necessary context 
(like paper names or topics) from the history. 

If the new question is already standalone and doesn't depend on history, return it unchanged.
Only output the rewritten question, nothing else.

Conversation history:
{history}

New question: {question}

Standalone question:"""


def rewrite_query(question, chat_history, max_history_turns=4):
    if not chat_history:
        return question

    # Only use the last few turns to keep the prompt short and fast
    recent = chat_history[-max_history_turns:]
    history_text = "\n".join(f"{turn['role']}: {turn['content']}" for turn in recent)

    llm = get_llm()
    prompt = REWRITE_PROMPT.format(history=history_text, question=question)
    response = llm.invoke(prompt)

    return response.content.strip()