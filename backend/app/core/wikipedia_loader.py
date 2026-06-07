"""
Fetches Wikipedia article revisions for use as benchmark documents.

Strategy: for a given article, fetch ~5 revisions evenly spaced through history,
extract clean text from each, ingest as ChronoLens document versions.
"""
import httpx
import re
from typing import List, Dict
from bs4 import BeautifulSoup

WIKI_API = "https://en.wikipedia.org/w/api.php"
MAX_TEXT_CHARS = 25000  # cap per revision to keep things tractable


class WikipediaLoader:
    def __init__(self):
        self.http = httpx.Client(
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; ChronoLens/1.0; +https://github.com/cycli-city/chronolens)",
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            },
            follow_redirects=True,
        )

    def fetch_revision_list(self, title: str, limit: int = 50) -> List[Dict]:
        try:
            resp = self.http.get(WIKI_API, params={
                "action": "query",
                "format": "json",
                "prop": "revisions",
                "titles": title,
                "rvlimit": limit,
                "rvprop": "ids|timestamp|comment",
                "rvslots": "main",
            })
            if resp.status_code != 200 or not resp.content:
                print(f"  Wikipedia API error: status {resp.status_code}")
                return []
            data = resp.json()
        except Exception as e:
            print(f"  Failed to fetch revision list: {e}")
            return []

        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return []
        page = next(iter(pages.values()))
        if "missing" in page:
            print(f"  Article not found: {title}")
            return []
        return page.get("revisions", [])
    
    def fetch_revision_content(self, revid: int) -> str:
        try:
            resp = self.http.get(WIKI_API, params={
                "action": "parse",
                "format": "json",
                "oldid": revid,
                "prop": "text",
                "disabletoc": 1,
                "formatversion": 2,
            })
            if resp.status_code != 200 or not resp.content:
                return ""
            data = resp.json()
        except Exception as e:
            print(f"  Failed to fetch revision {revid}: {e}")
            return ""

        try:
            return self._clean_html(data["parse"]["text"])
        except KeyError:
            return ""

    def _clean_html(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        # Strip noise
        for selector in [
            ".reference", ".reflist", ".navbox", ".infobox",
            ".mw-editsection", ".thumb", ".gallery", ".hatnote",
            ".sistersitebox", "table", "sup", "style", "script",
            "#References", ".mw-references-wrap",
        ]:
            for tag in soup.select(selector):
                tag.decompose()

        # Pull only meaningful paragraph-style content
        pieces = []
        for el in soup.find_all(["p", "h2", "h3", "li"]):
            txt = el.get_text(separator=" ", strip=True)
            if len(txt) > 20:
                pieces.append(txt)

        text = "\n".join(pieces)
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\[\d+\]", "", text)  # remove [1] citations
        return text[:MAX_TEXT_CHARS].strip()

    def fetch_revisions_for_article(
        self, title: str, n_versions: int = 5
    ) -> List[Dict]:
        """Return up to n_versions evenly-spaced revisions, oldest-first."""
        all_revs = self.fetch_revision_list(title, limit=50)
        if not all_revs:
            return []

        # Evenly space across history
        step = max(len(all_revs) // n_versions, 1)
        picked = all_revs[::step][:n_versions]
        picked.reverse()  # oldest-first

        results = []
        for i, rev in enumerate(picked, start=1):
            content = self.fetch_revision_content(rev["revid"])
            if not content or len(content) < 500:
                continue
            results.append({
                "version": i,
                "revid": rev["revid"],
                "timestamp": rev["timestamp"][:10],  # YYYY-MM-DD
                "comment": rev.get("comment", ""),
                "content": content,
            })
        return results