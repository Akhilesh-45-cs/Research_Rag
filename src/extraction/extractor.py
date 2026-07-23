import os
import fitz  # pymupdf
import pdfplumber

PAPERS_DIR = "data/documents"
OUTPUT_DIR = "data/cache/extracted_text"

os.makedirs(OUTPUT_DIR, exist_ok=True)


def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()

    # Fix common encoding artifacts from PDF font mapping issues
    replacements = {
        "ΓÇÖ": "'", "ΓÇ£": '"', "ΓÇ¥": '"', "ΓÇô": "-", "ΓÇô": "–",
        "∩¼é": "fl", "∩¼ü": "fi", "≡¥æ": "", "≡¥É": ""
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)

    return text


def extract_all_papers():
    pdf_files = [f for f in os.listdir(PAPERS_DIR) if f.endswith(".pdf")]
    print(f"Found {len(pdf_files)} PDFs")

    for filename in pdf_files:
        pdf_path = os.path.join(PAPERS_DIR, filename)
        text = extract_text_from_pdf(pdf_path)

        print(f"  Extracting tables from {filename}...")
        table_text = extract_tables_from_pdf(pdf_path)
        full_text = text + "\n\n" + table_text

        output_filename = filename.replace(".pdf", ".txt")
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_text)

        print(f"Processed: {filename} -> {output_filename} ({len(full_text)} characters)")


def extract_tables_from_pdf(pdf_path):
    """Extracts tables as readable text blocks, tagged so we know they're tables."""
    table_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for table in tables:
                table_text += f"\n[TABLE - Page {page_num + 1}]\n"
                for row in table:
                    clean_row = [str(cell) if cell else "" for cell in row]
                    table_text += " | ".join(clean_row) + "\n"
                table_text += "[END TABLE]\n\n"
    return table_text


if __name__ == "__main__":
    extract_all_papers()