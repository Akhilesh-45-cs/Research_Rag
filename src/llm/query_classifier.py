from src.llm.groq_client import get_llm

CLASSIFY_PROMPT = """You are a classifier for a research paper assistant.
Classify the user's message into exactly one category:

- "greeting" - hi, hello, thanks, casual small talk with no real question
- "irrelevant" - a real question, but unrelated to research/academic topics (e.g. food, weather, sports)
- "research" - a question about research papers, academic topics, or anything that could be answered using research papers

Respond with ONLY one word: greeting, irrelevant, or research

Message: {message}

Classification:"""


def classify_query(message):
    llm = get_llm()
    prompt = CLASSIFY_PROMPT.format(message=message)
    response = llm.invoke(prompt)

    label = response.content.strip().lower()

    # safety fallback in case model adds extra words
    if "greeting" in label:
        return "greeting"
    elif "irrelevant" in label:
        return "irrelevant"
    else:
        return "research"
