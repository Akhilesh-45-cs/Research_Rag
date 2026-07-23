import requests
import xml.etree.ElementTree as ET

ARXIV_API_URL = "http://export.arxiv.org/api/query"

# arXiv's Atom XML uses this namespace
NS = {"atom": "http://www.w3.org/2005/Atom"}


def search_arxiv(query, max_results=5):
    """
    Searches arXiv for papers matching a topic query.
    Returns a list of dicts: title, authors, summary, pdf_url, arxiv_id
    """
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending"
    }

    response = requests.get(ARXIV_API_URL, params=params)
    response.raise_for_status()

    root = ET.fromstring(response.text)
    entries = root.findall("atom:entry", NS)

    results = []
    for entry in entries:
        title = entry.find("atom:title", NS).text.strip().replace("\n", " ")
        summary = entry.find("atom:summary", NS).text.strip().replace("\n", " ")
        arxiv_id = entry.find("atom:id", NS).text.strip().split("/abs/")[-1]

        authors = [a.find("atom:name", NS).text for a in entry.findall("atom:author", NS)]

        pdf_url = None
        for link in entry.findall("atom:link", NS):
            if link.get("title") == "pdf":
                pdf_url = link.get("href")
        if not pdf_url:
            # fallback: arXiv pdf urls follow a predictable pattern
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        results.append({
            "title": title,
            "authors": authors,
            "summary": summary,
            "pdf_url": pdf_url,
            "arxiv_id": arxiv_id
        })

    return results


if __name__ == "__main__":
    results = search_arxiv("EV battery health monitoring", max_results=5)
    for r in results:
        print(f"\nTitle: {r['title']}")
        print(f"Authors: {', '.join(r['authors'][:3])}")
        print(f"arXiv ID: {r['arxiv_id']}")
        print(f"PDF: {r['pdf_url']}")