import os
import requests
import time
from dotenv import load_dotenv

load_dotenv()

CORE_API_URL = "https://api.core.ac.uk/v3/search/works"


def search_core(query, max_results=5, max_retries=2, timeout=45):
    api_key = os.getenv("CORE_API_KEY")
    headers = {"Authorization": f"Bearer {api_key}"}

    params = {
        "q": query,
        "limit": max_results * 3
    }

    data = None

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(CORE_API_URL, headers=headers, params=params, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            break
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
            if attempt < max_retries:
                wait_time = 3 * (attempt + 1)
                print(f"CORE API connection issue. Retrying in {wait_time}s ({attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
                continue
            else:
                print("CORE API unavailable after all retries. It may be temporarily overloaded - try again shortly.")
                return []
        except requests.exceptions.RequestException as e:
            print(f"CORE API request failed: {e}")
            return []

    if data is None:
        return []

    results = []
    for item in data.get("results", []):
        primary_url = item.get("downloadUrl")
        fallback_urls = item.get("sourceFulltextUrls") or []
        pdf_url = primary_url or (fallback_urls[0] if fallback_urls else None)
        if not pdf_url:
            continue

        results.append({
            "title": item.get("title", "Untitled"),
            "authors": [a.get("name", "") for a in item.get("authors", [])],
            "summary": item.get("abstract") or "",
            "pdf_url": pdf_url,
            "fallback_urls": fallback_urls,
            "core_id": item.get("id", ""),
            "year": item.get("yearPublished"),
        })

        if len(results) >= max_results:
            break

    return results


if __name__ == "__main__":
    results = search_core("lithium-ion battery state of health estimation", max_results=5)
    for r in results:
        print(f"\nTitle: {r['title']}")
        print(f"Authors: {', '.join(r['authors'][:3])}")
        print(f"Year: {r['year']}")
        print(f"PDF: {r['pdf_url']}")

    if not results:
        print("No results with downloadable PDFs found.")