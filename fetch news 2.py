import json, re, html, hashlib, os, time
from datetime import datetime, timezone

import socket
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
MAX_NEW_PER_RUN = 120

# filter=True يعني الموقع عام، فنأخذ منه أخبار الذكاء الاصطناعي بس
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

DATA_FILE = "news.json"
translator = GoogleTranslator(source="en", target="ar")


def clean(text, limit=400):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].rsplit(" ", 1)[0] + "…" if len(text) > limit else text


def translate(text):
    if not text:
        return ""
    try:
        time.sleep(0.2)
        return translator.translate(text[:4500])
    except Exception as e:
        print("translate failed:", e)
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
            parsed = feedparser.parse(feed["url"])
            entries = parsed.entries
        except Exception as e:
            print("feed failed:", feed["name"], e)
            continue

        print(feed["name"], len(entries), "entries")
        for e in entries[:MAX_PER_FEED]:
            if new_count >= MAX_NEW_PER_RUN:
                break
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
                "title_ar": translate(title),
                "summary_ar": translate(summary),
                "link": link,
                "date": dt.isoformat(),
            })
            seen.add(uid)
            new_count += 1

    items.sort(key=lambda x: x["date"], reverse=True)
    items = items[:5000]
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    print("added", new_count, "new items, total", len(items))


if __name__ == "__main__":
    main()
