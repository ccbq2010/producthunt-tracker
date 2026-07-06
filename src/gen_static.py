#!/usr/bin/env python3
"""Generate a static HTML page for GitHub Pages."""

import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "data/producthunt.db"
OUTPUT = sys.argv[2] if len(sys.argv) > 2 else "public/index.html"


def generate(db_path: str) -> str:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    rows = conn.execute("""
        SELECT p.name, p.tagline, p.description_zh, p.description, p.website,
               p.votes_count_ongoing AS votes,
               p.comments_count_ongoing AS comments,
               p.votes_count_ongoing - COALESCE(snap.votes_count, 0) AS vote_delta,
               p.comments_count_ongoing - COALESCE(snap.comments_count, 0) AS comment_delta,
               p.topics
        FROM posts p
        LEFT JOIN (
            SELECT s.post_id, s.votes_count, s.comments_count
            FROM snapshots s
            INNER JOIN (
                SELECT post_id, MAX(captured_at) AS latest
                FROM snapshots WHERE captured_at < ?
                GROUP BY post_id
            ) latest ON s.post_id = latest.post_id AND s.captured_at = latest.latest
        ) snap ON p.id = snap.post_id
        WHERE p.last_seen_at >= ?
        ORDER BY vote_delta DESC
        LIMIT 30
    """, (cutoff, cutoff)).fetchall()
    conn.close()

    products = []
    for r in rows:
        d = dict(r)
        d["topics"] = json.loads(d.get("topics", "[]"))
        d["score"] = round(
            (d["votes"] + d["comments"] * 2) +
            0.5 * (d.get("vote_delta", 0) + d.get("comment_delta", 0) * 1.5), 1
        )
        # Use Chinese description if available, fallback to English
        # Use Chinese description if available, fallback to English
        d["desc"] = (d.get("description_zh") or d.get("description") or "").strip()
        if len(d["desc"]) > 350:
            d["desc"] = d["desc"][:347] + "..."
        products.append(d)

    products.sort(key=lambda x: x["score"], reverse=True)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    products_html = ""
    for i, p in enumerate(products, 1):
        tags = "".join(
            f'<span class="tag">{t}</span>' for t in p.get("topics", [])[:4]
        )
        website = p.get("website", "")
        link = f'<a href="{website}" target="_blank" rel="noopener">访问官网 →</a>' if website else ""
        products_html += f"""
<article class="product">
  <span class="rank">{i}</span>
  <div class="name">{p['name']}</div>
  <div class="tagline">{p.get('tagline', '')}</div>
  <div class="desc">{p['desc']}</div>
  <div class="meta">
    <span>👍 {p['votes']}</span>
    <span>💬 {p['comments']}</span>
    <span>🔥 {p['score']}</span>
    {link}
  </div>
  <div class="meta tags">{tags}</div>
</article>"""

    if not products:
        products_html = '<div class="empty"><p>暂无数据，稍后再来。</p></div>'

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Product Hunt 每日趋势</title>
<meta name="description" content="Product Hunt 热门产品每日追踪">
<style>
:root {{ --ph: #da552f; --bg: #fafafa; --card: #fff; --text: #333; --muted: #888; --border: #eee; --rank-bg: #da552f; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC", sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}
header {{ background: linear-gradient(135deg, #da552f 0%, #b8441f 100%); color: #fff; padding: 28px 24px; text-align: center; }}
header h1 {{ font-size: 24px; font-weight: 700; margin-bottom: 6px; }}
header p {{ font-size: 14px; opacity: 0.85; }}
.container {{ max-width: 800px; margin: 0 auto; padding: 20px 16px; }}
.product {{ background: var(--card); border-radius: 12px; padding: 18px; margin-bottom: 14px; border: 1px solid var(--border); transition: box-shadow 0.2s; }}
.product:hover {{ box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
.product .rank {{ display: inline-flex; align-items: center; justify-content: center; width: 26px; height: 26px; line-height: 1; background: var(--rank-bg); color: #fff; border-radius: 50%; font-size: 12px; font-weight: 700; margin-right: 10px; vertical-align: middle; }}
.product .name {{ font-weight: 600; font-size: 16px; vertical-align: middle; }}
.product .tagline {{ color: var(--muted); font-size: 13px; margin: 6px 0 8px 36px; }}
.product .desc {{ color: #555; font-size: 13px; line-height: 1.8; margin: 0 0 10px 0; }}
.product .meta {{ font-size: 12px; color: var(--muted); }}
.product .meta span {{ margin-right: 14px; }}
.product .tags {{ margin-top: 6px; }}
.product a {{ color: var(--ph); text-decoration: none; font-size: 12px; font-weight: 500; }}
.product a:hover {{ text-decoration: underline; }}
.tag {{ display: inline-block; background: #f0f0f0; padding: 2px 8px; border-radius: 8px; font-size: 11px; margin-right: 4px; color: #666; }}
.empty {{ text-align: center; padding: 60px 20px; color: var(--muted); }}
footer {{ text-align: center; padding: 24px 20px; color: var(--muted); font-size: 12px; }}
@media (max-width: 480px) {{
  header h1 {{ font-size: 20px; }}
  .product {{ padding: 14px; }}
  .product .tagline, .product .desc {{ margin-left: 0; margin-top: 8px; }}
}}
</style>
</head>
<body>
<header>
  <h1>Product Hunt · 每日趋势</h1>
  <p>热门产品追踪 · 更新于 {now}</p>
</header>
<main class="container">
{products_html}
</main>
<footer>
  <p>数据来源 <a href="https://www.producthunt.com" target="_blank" rel="noopener" style="color:var(--ph);">Product Hunt</a> · 由 GitHub Actions 每日自动更新</p>
</footer>
</body>
</html>"""


if __name__ == "__main__":
    import os
    html = generate(DB_PATH)
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ Generated {OUTPUT}")
