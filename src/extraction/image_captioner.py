import re
import fitz
import base64
from src.llm.groq_client import get_vision_llm
from langchain_core.messages import HumanMessage

CAPTION_PROMPT = """Describe this figure from a research paper in 2-4 sentences. 
If it's a chart, graph, or plot, describe what it shows, the trend, and any 
visible numbers or axis labels. If it's a confusion matrix, describe the values 
and what they indicate. If it's a diagram, describe its structure and purpose. 
Be specific and factual - do not guess at values you cannot actually see clearly.

Respond with ONLY the final description - no reasoning, no self-correction, 
no <think> tags, just the finished 2-4 sentence description."""


def strip_thinking(text):
    """Removes <think>...</think> reasoning blocks some models include."""
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return cleaned.strip()


def extract_images_from_pdf(pdf_path, min_size_bytes=20000):
    """
    Extracts embedded images from a PDF. Skips small images (likely icons, 
    logos, license badges - not meaningful figures) using a size threshold.
    """
    doc = fitz.open(pdf_path)
    images = []

    for page_num, page in enumerate(doc):
        image_list = page.get_images(full=True)
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]

            if len(image_bytes) < min_size_bytes:
                continue

            width = base_image.get("width", 0)
            height = base_image.get("height", 0)
            if width < 150 or height < 150:
                continue  # skip small/thin images - unlikely to be real figures

            images.append({
                "page_num": page_num + 1,
                "image_bytes": image_bytes,
                "image_ext": base_image["ext"]
            })

    doc.close()
    return images


def caption_image(image_bytes, image_ext):
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:image/{image_ext};base64,{b64_image}"

    llm = get_vision_llm()
    message = HumanMessage(
        content=[
            {"type": "text", "text": CAPTION_PROMPT},
            {"type": "image_url", "image_url": {"url": data_url}}
        ]
    )

    try:
        response = llm.invoke([message])
        cleaned = strip_thinking(response.content)
        return cleaned if cleaned else None
    except Exception:
        return None


def extract_and_caption_images(pdf_path, max_images=15):
    images = extract_images_from_pdf(pdf_path)

    if len(images) > max_images:
        images = images[:max_images]

    captioned = []
    for img in images:
        caption = caption_image(img["image_bytes"], img["image_ext"])
        if caption:
            captioned.append({"page_num": img["page_num"], "caption": caption})

    return captioned


if __name__ == "__main__":
    test_pdf = "data/documents/batteries-09-00539-v3.pdf"
    results = extract_and_caption_images(test_pdf, max_images=5)

    print(f"Captioned {len(results)} images\n")
    for r in results:
        print(f"--- Page {r['page_num']} ---")
        print(r["caption"])
        print()