"""Minimal web server — shows PH trending products only."""

import http.server
import json
import logging
import os
import sqlite3
import urllib.parse
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

PAGE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PH Trends</title>
<style>
body {{ font-family: -apple-system, sans-serif; max-width: 780px; margin: 0 auto; padding: 20px; color: #333; background: #fafafa; }}
h1 {{ font-size: 22px; color: #da552f; margin-bottom: 4px; }}
.sub {{ color: #999; font-size: 13px; margin-bottom: 24px; }}
.product {{ background: #fff; border-radius: 10px; padding: 16px; margin-bottom: 12px; border: 1px solid #eee; }}
.product .rank {{ display: inline-block; width: 22px; height: 22px; line-height: 22px; text-align: center; background: #da552f; color: #fff; border-radius: 50%; font-size: 11px; font-weight: 700; margin-right: 8px; }}
.product .name {{ font-weight: 600; font-size: 15px; }}
.product .tagline {{ color: #666; font-size: 13px; margin: 6px 0 6px 30px; }}
.product .meta {{ font-size: 12px; color: #999; margin-left: 30px; }}
.product .meta span {{ margin-right: 14px; }}
.product a {{ color: #da552f; text-decoration: none; }}
.product .desc {{ color: #555; font-size: 13px; margin: 8px 0 8px 0; line-height: 1.7; }}
.tag {{ display: inline-block; background: #f0f0f0; padding: 2px 7px; border-radius: 8px; font-size: 11px; margin-right: 4px; }}
.empty {{ text-align: center; padding: 60px 20px; color: #999; }}
</style>
</head>
<body>
<h1>Product Hunt · 每日趋势榜</h1>
<div class="sub">抓取 Product Hunt 上 AI、SaaS、开发工具等热门产品，按投票增速和互动热度排序。数据每次执行 <code>python main.py fetch</code> 后更新。</div>
{content}
</body>
</html>"""

EMPTY_HTML = '<div class="empty"><p>No data yet.</p><p><code>python main.py fetch</code> to get started.</p></div>'


class Handler(http.server.BaseHTTPRequestHandler):
    db_path = "data/producthunt.db"

    def do_GET(self):
        if self.path.rstrip("/") in ("", "/"):
            self._index()
        else:
            self.send_response(404)
            self.end_headers()

    def _index(self):
        products = self._get_products()
        if not products:
            content = EMPTY_HTML
        else:
            rows = []
            for i, p in enumerate(products, 1):
                tags = "".join(f'<span class="tag">{t}</span>' for t in p.get("topics", [])[:4])
                website = p.get("website", "")
                link = f'<a href="{website}" target="_blank">访问官网 →</a>' if website else ""
                desc = p.get("description_zh", "").strip() or p.get("description", "").strip()
                if desc and len(desc) > 300:
                    desc = desc[:297] + "..."
                
                rows.append(f"""<div class="product">
    <span class="rank">{i}</span>
    <div class="name">{p['name']}</div>
    <div class="tagline">{p.get('tagline', '')}</div>
    <div class="desc">{desc}</div>
    <div class="meta">
        <span>👍 {p.get('votes', 0)} votes</span>
        <span>💬 {p.get('comments', 0)} 评论</span>
        <span>🔥 热度 {p.get('score', 0)}</span>
        {link}
    </div>
    <div class="meta" style="margin-top:4px;">{tags}</div>
</div>""")
            content = "\n".join(rows)

        html = PAGE.format(
            updated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            content=content,
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _get_products(self) -> list[dict]:
        if not os.path.exists(self.db_path):
            return []
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        rows = conn.execute("""
            SELECT p.name, p.tagline, p.description_zh, p.website,
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
            LIMIT 20
        """, (cutoff, cutoff)).fetchall()
        conn.close()

        results = []
        for r in rows:
            d = dict(r)
            d["topics"] = json.loads(d.get("topics", "[]"))
            d["score"] = round(
                (d["votes"] + d["comments"] * 2) +
                0.5 * (d.get("vote_delta", 0) + d.get("comment_delta", 0) * 1.5), 1
            )
            results.append(d)
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def log_message(self, fmt, *args):
        pass


def serve(db_path: str = "data/producthunt.db", port: int = 8000):
    Handler.db_path = db_path
    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    print(f"PH Trends at http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    serve()
