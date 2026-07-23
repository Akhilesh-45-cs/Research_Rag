import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

def get_llm():
    """Main generation model - migrated from deprecated llama-3.3-70b-versatile."""
    api_key = os.getenv("GROQ_API_KEY")
    llm = ChatGroq(
        model="openai/gpt-oss-120b",
        groq_api_key=api_key,
        temperature=0.2
    )
    return llm


def get_fast_llm():
    """Smaller, faster model for routing/classification - migrated from 
    deprecated llama-3.1-8b-instant."""
    api_key = os.getenv("GROQ_API_KEY")
    llm = ChatGroq(
        model="openai/gpt-oss-20b",
        groq_api_key=api_key,
        temperature=0.0
    )
    return llm


def get_vision_llm():
    """Vision-capable model for image/figure captioning. Currently a preview 
    model on Groq - treat as experimental, may need adjustment if Groq changes 
    availability."""
    api_key = os.getenv("GROQ_API_KEY")
    llm = ChatGroq(
        model="qwen/qwen3.6-27b",
        groq_api_key=api_key,
        temperature=0.3
    )
    return llm