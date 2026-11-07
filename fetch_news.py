import json, re, html, hashlib, os, time, socket
from datetime import datetime, timezone

import requests
import feedparser
from deep_translator import GoogleTranslator

socket.setdefaulttimeout(20)
_orig_request = requests.Session.request


def _request_with_timeout(self, *a, **kw):
    kw.setdefault("timeout", 15)
    return _orig_request(self, *a, **kw)


requests.Session.request = _request_with_timeout

MAX_PER_FEED = 30
MAX_TRANSLATE_PER_RUN = 300
DATA_FILE = "news.json"

FEEDS = [
    {"name": "NYT", "url": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml", "filter": True},
    {"name": "BBC", "url": "http://feeds.bbci.co.uk/news/technology/rss.xml", "filter": True},
    {"name": "Guardian", "url": "https://www.theguardian.com/technology/artificialintelligenceai/rss", "filter": False},
    {"name": "Wired", "url": "https://www.wired.com/feed/tag/ai/latest/rss", "filter": False},
    {"name": "MIT Tech Review", "url": "https://www.technologyreview.com/feed/", "filter": True},
    {"name": "TechCrunch", "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "filter": False},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "filter": False},
    {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/technology-lab", "filter": True},
    {"name": "VentureBeat", "url": "https://venturebeat.com/category/ai/feed/", "filter": False},
    {"name": "OpenAI", "url": "https://openai.com/news/rss.xml", "filter": False},
    {"name": "Google AI", "url": "https://blog.google/technology/ai/rss/", "filter": False},
]

KEYWORDS = re.compile(
    r"\b(AI|A\.I\.|artificial intelligence|ChatGPT|OpenAI|LLMs?|machine learning|"
    r"Gemini|Claude|Anthropic|chatbots?|generative|deepseek|neural network)\b",
    re.IGNORECASE,
)

translator = GoogleTranslator(source="en", target="ar")
done = 0
fails_in_row = 0


def clean(text, limit=400):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].rsplit(" ", 1)[0] + "…" if len(text) > limit else text


def translate(text):
    global done, fails_in_row
    if not text or done >= MAX_TRANSLATE_PER_RUN or fails_in_row >= 5:
        return ""
    for _ in range(2):
        try:
            time.sleep(0.3)
            out = translator.translate(text[:4500])
            if out:
                done += 1
                fails_in_row = 0
                return out
        except Exception as e:
            print("translate failed:", repr(e)[:200])
            time.sleep(2)
    fails_in_row += 1
    return ""


def load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def main():
    items = load()
    seen = {i["id"] for i in items}
    new_count = 0

    for feed in FEEDS:
        try:
            entries = feedparser.parse(feed["url"]).entries
        except Exception as e:
            print("feed failed:", feed["name"], e)
            continue

        print(feed["name"], len(entries), "entries")
        for e in entries[:MAX_PER_FEED]:
            link = e.get("link", "")
            if not link:
                continue
            uid = hashlib.md5(link.encode()).hexdigest()
            if uid in seen:
                continue

            title = clean(e.get("title", ""), 300)
            summary = clean(e.get("summary", ""))
            if feed["filter"] and not KEYWORDS.search(title + " " + summary):
                continue

            if e.get("published_parsed"):
                dt = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            items.append({
                "id": uid,
                "source": feed["name"],
                "title": title,
                "summary": summary,
                "title_ar": "",
                "summary_ar": "",
                "link": link,
                "date": dt.isoformat(),
            })
            seen.add(uid)
            new_count += 1

    items.sort(key=lambda x: x["date"], reverse=True)
    items = items[:5000]

    for i in items:
        if i.get("title") and not i.get("title_ar"):
            i["title_ar"] = translate(i["title"])
        if i.get("summary") and not i.get("summary_ar"):
            i["summary_ar"] = translate(i["summary"])

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)

    missing = sum(1 for i in items if not i.get("title_ar"))
    print("added", new_count, "| translated", done, "| still untranslated", missing, "| total", len(items))


if __name__ == "__main__":
    main()
