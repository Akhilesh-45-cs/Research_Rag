import os
import re
from langchain.text_splitter import RecursiveCharacterTextSplitter

INPUT_DIR = "data/cache/extracted_text"
OUTPUT_DIR = "data/cache/chunks"

os.makedirs(OUTPUT_DIR, exist_ok=True)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Common research paper section names we try to detect
SECTION_KEYWORDS = [
    "abstract", "introduction", "related work", "literature review",
    "background", "methodology", "methods", "materials and methods",
    "proposed method", "proposed approach", "experimental setup",
    "experiments", "results", "results and discussion", "discussion",
    "conclusion", "conclusions", "future work", "references",
    "acknowledgment", "acknowledgement"
]

# Matches lines like: "1. Introduction", "II. RELATED WORK", "Abstract", "3.2 Methodology"
HEADING_PATTERN = re.compile(
    r"^\s*((\d+(\.\d+)*\.?)|([IVXLC]+\.))?\s*(" + "|".join(SECTION_KEYWORDS) + r")\s*$",
    re.IGNORECASE
)

def normalize_section_name(raw_name):
    """Maps messy heading variants to a clean, consistent category."""
    name = raw_name.lower().strip()

    if "abstract" in name:
        return "abstract"
    if "introduction" in name:
        return "introduction"
    if "related work" in name or "literature review" in name or "background" in name:
        return "related_work"
    if "method" in name or "approach" in name or "experimental setup" in name:
        return "methods"
    if "result" in name or "discussion" in name:
        return "results"
    if "conclusion" in name or "future work" in name:
        return "conclusion"
    if "reference" in name:
        return "references"
    if "acknowledg" in name:
        return "acknowledgment"
    return "header"

def split_into_sections(text):
    """Splits raw text into a list of (section_name, section_text) tuples."""
    lines = text.split("\n")
    sections = []
    current_section = "header"  # text before any recognized heading
    current_text = []

    for line in lines:
        stripped = line.strip()
        match = HEADING_PATTERN.match(stripped) if stripped else None

        # Only treat as heading if line is short (real headings aren't full sentences)
        if match and len(stripped) < 60:
            # save previous section before starting new one
            if current_text:
                sections.append((current_section, "\n".join(current_text)))
            current_section = normalize_section_name(stripped)
            current_text = []
        else:
            current_text.append(line)

    if current_text:
        sections.append((current_section, "\n".join(current_text)))

    return sections


def load_text_files():
    texts = {}
    for filename in os.listdir(INPUT_DIR):
        if filename.endswith(".txt"):
            path = os.path.join(INPUT_DIR, filename)
            with open(path, "r", encoding="utf-8") as f:
                texts[filename] = f.read()
    return texts


def chunk_all_papers():
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    texts = load_text_files()
    print(f"Found {len(texts)} text files")

    for filename, text in texts.items():
        sections = split_into_sections(text)

        base_name = filename.replace(".txt", "")
        output_path = os.path.join(OUTPUT_DIR, f"{base_name}_chunks.txt")

        chunk_count = 0
        with open(output_path, "w", encoding="utf-8") as f:
            for section_name, section_text in sections:
                if not section_text.strip():
                    continue

                chunks = splitter.split_text(section_text)
                for chunk in chunks:
                    f.write(f"--- CHUNK {chunk_count} | SECTION: {section_name} ---\n")
                    f.write(chunk)
                    f.write("\n\n")
                    chunk_count += 1

        print(f"{filename}: {chunk_count} chunks across {len(sections)} sections -> {output_path}")


if __name__ == "__main__":
    chunk_all_papers()