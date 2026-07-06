"""Translate product descriptions to Chinese using AI."""
import json
import sqlite3
import urllib.request
import os

PH_API = "https://api.producthunt.com/v2/api/graphql"

def get_pending_translations(db_path: str = "data/producthunt.db") -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT p.id, p.name, p.tagline, p.description, p.topics
        FROM posts p
        WHERE p.description != ''
          AND (p.description_zh IS NULL OR p.description_zh LIKE '%需要接入翻译API%')
        ORDER BY p.votes_count_ongoing DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def translate_with_free_api(text: str) -> str | None:
    """Use a free translation API (LibreTranslate compatible)."""
    if not text or len(text.strip()) < 10:
        return None
    
    url = "https://libretranslate.com/translate"
    body = json.dumps({
        "q": text[:500],
        "source": "en",
        "target": "zh",
        "format": "text",
    }).encode("utf-8")
    
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
    }, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            translated = data.get("translatedText", "")
            # Verify it contains Chinese characters
            if any('\u4e00' <= c <= '\u9fff' for c in translated):
                return translated
    except Exception as e:
        print(f"Translation API error: {e}")
    return None


def update_chinese_description(db_path: str, post_id: str, zh_text: str):
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE posts SET description_zh = ? WHERE id = ?", (zh_text, post_id))
    conn.commit()
    conn.close()


def main():
    db_path = "data/producthunt.db"
    pending = get_pending_translations(db_path)
    print(f"Found {len(pending)} descriptions to translate")
    
    for p in pending:
        pid = p["id"]
        name = p["name"]
        desc = p.get("description", "")
        tagline = p.get("tagline", "")
        
        # Combine tagline and description for context
        full_text = f"{tagline}. {desc}" if tagline else desc
        full_text = full_text[:400]
        
        print(f"Translating: {name}...", end=" ")
        
        result = translate_with_free_api(full_text)
        if result:
            print(f"OK ({len(result)} chars)")
            update_chinese_description(db_path, pid, result)
        else:
            print("FALLBACK")
            # Fallback: keep English but mark clearly
            zh = f"【{name}】\n简介：{tagline}\n\n{description_shortened(desc)}"
            update_chinese_description(db_path, pid, zh)


def description_shortened(desc: str, max_len: int = 200) -> str:
    if len(desc) <= max_len:
        return desc
    return desc[:max_len-3] + "..."


if __name__ == "__main__":
    main()
