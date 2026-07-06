import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS posts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                tagline TEXT DEFAULT '',
                description TEXT DEFAULT '',
                url TEXT DEFAULT '',
                website TEXT DEFAULT '',
                votes_count_ongoing INTEGER DEFAULT 0,
                comments_count_ongoing INTEGER DEFAULT 0,
                created_at TEXT,
                description_zh TEXT DEFAULT '',
                author TEXT DEFAULT '',
                topics TEXT DEFAULT '[]',
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT NOT NULL,
                votes_count INTEGER NOT NULL,
                comments_count INTEGER NOT NULL,
                captured_at TEXT NOT NULL,
                FOREIGN KEY (post_id) REFERENCES posts(id)
            );

            CREATE INDEX IF NOT EXISTS idx_snapshots_post_id ON snapshots(post_id);
            CREATE INDEX IF NOT EXISTS idx_snapshots_captured ON snapshots(captured_at);
        """)
        self.conn.commit()

    def upsert_posts(self, posts: list[dict]):
        now = datetime.utcnow().isoformat()
        for post in posts:
            topics_json = json.dumps(post.get("topics", []))
            pid = post["id"]

            existing = self.conn.execute(
                "SELECT votes_count_ongoing FROM posts WHERE id = ?", (pid,)
            ).fetchone()

            if existing:
                self.conn.execute("""
                    UPDATE posts SET
                        votes_count_ongoing = ?,
                        comments_count_ongoing = ?,
                        last_seen_at = ?
                    WHERE id = ?
                """, (
                    post["votes_count"],
                    post["comments_count"],
                    now, pid,
                ))
            else:
                self.conn.execute("""
                    INSERT INTO posts
                    (id, name, tagline, description, url, website,
                     votes_count_ongoing, comments_count_ongoing,
                     created_at, author, topics, first_seen_at, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pid, post["name"], post["tagline"], post.get("description", ""),
                    post.get("url", ""), post.get("website", ""),
                    post["votes_count"], post["comments_count"],
                    post.get("created_at", ""),
                    post.get("author", ""), topics_json, now, now,
                ))

            self.conn.execute("""
                INSERT INTO snapshots (post_id, votes_count, comments_count, captured_at)
                VALUES (?, ?, ?, ?)
            """, (pid, post["votes_count"], post["comments_count"], now))

        self.conn.commit()
        logger.info(f"Upserted {len(posts)} posts, {len(posts)} snapshots")

    def get_trending(self, hours: int = 24, limit: int = 20) -> list[dict]:
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        rows = self.conn.execute("""
            SELECT p.*,
                   COALESCE(snap.votes_count, 0) AS prev_votes,
                   COALESCE(snap.comments_count, 0) AS prev_comments,
                   p.votes_count_ongoing - COALESCE(snap.votes_count, 0) AS vote_delta,
                   p.comments_count_ongoing - COALESCE(snap.comments_count, 0) AS comment_delta
            FROM posts p
            LEFT JOIN (
                SELECT s.post_id, s.votes_count, s.comments_count
                FROM snapshots s
                INNER JOIN (
                    SELECT post_id, MAX(captured_at) AS latest
                    FROM snapshots
                    WHERE captured_at < ?
                    GROUP BY post_id
                ) latest ON s.post_id = latest.post_id AND s.captured_at = latest.latest
            ) snap ON p.id = snap.post_id
            WHERE p.last_seen_at >= ?
            ORDER BY vote_delta DESC
            LIMIT ?
        """, (cutoff, cutoff, limit)).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["topics_raw"] = json.loads(d.get("topics", "[]"))
            results.append(d)
        return results

    def get_velocity(self, days: int = 7, limit: int = 20) -> list[dict]:
        """Posts with highest vote velocity over N days."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        rows = self.conn.execute("""
            SELECT p.name, p.tagline, p.website, p.author, p.topics,
                   first_snap.votes_count AS start_votes,
                   p.votes_count_ongoing AS end_votes,
                   p.votes_count_ongoing - first_snap.votes_count AS total_gain,
                   (p.votes_count_ongoing - first_snap.votes_count)
                       / MAX(CAST(julianday('now') - julianday(first_snap.captured_at) AS REAL), 0.04)
                       AS velocity_per_day
            FROM posts p
            INNER JOIN (
                SELECT post_id, votes_count, captured_at
                FROM snapshots s1
                WHERE captured_at = (
                    SELECT MIN(captured_at) FROM snapshots s2
                    WHERE s2.post_id = s1.post_id AND s2.captured_at >= ?
                )
            ) first_snap ON p.id = first_snap.post_id
            WHERE p.last_seen_at >= ?
              AND CAST(julianday('now') - julianday(first_snap.captured_at) AS REAL) >= 0.04
            ORDER BY velocity_per_day DESC
            LIMIT ?
        """, (cutoff, cutoff, limit)).fetchall()
        return [dict(r) for r in rows]

    def get_topic_distribution(self, hours: int = 168) -> dict[str, int]:
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        rows = self.conn.execute("""
            SELECT topics FROM posts WHERE last_seen_at >= ?
        """, (cutoff,)).fetchall()

        counter: dict[str, int] = {}
        for row in rows:
            topics = json.loads(row["topics"])
            for t in topics:
                counter[t] = counter.get(t, 0) + 1
        return dict(sorted(counter.items(), key=lambda x: x[1], reverse=True))

    def cleanup_old_snapshots(self, keep_days: int = 90):
        cutoff = (datetime.utcnow() - timedelta(days=keep_days)).isoformat()
        result = self.conn.execute(
            "DELETE FROM snapshots WHERE captured_at < ?", (cutoff,)
        )
        self.conn.commit()
        if result.rowcount:
            logger.info(f"Cleaned up {result.rowcount} old snapshots")

    def close(self):
        self.conn.close()
