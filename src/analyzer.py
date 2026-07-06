import logging
from collections import Counter

logger = logging.getLogger(__name__)


class Analyzer:
    def __init__(self, min_votes: int = 50, top_n: int = 10):
        self.min_votes = min_votes
        self.top_n = top_n

    def compute_trending_score(self, post: dict) -> float:
        votes = post.get("votes_count_ongoing", 0)
        comments = post.get("comments_count_ongoing", 0)
        vote_delta = post.get("vote_delta", 0)
        comment_delta = post.get("comment_delta", 0)

        base = votes + comments * 2
        momentum = vote_delta + comment_delta * 1.5
        return base + momentum * 0.5

    def rank_trending(self, posts: list[dict]) -> list[dict]:
        scored = []
        for p in posts:
            if p.get("votes_count_ongoing", 0) < self.min_votes:
                continue
            p["trend_score"] = round(self.compute_trending_score(p), 1)
            scored.append(p)
        scored.sort(key=lambda x: x["trend_score"], reverse=True)
        return scored[:self.top_n]

    def analyze_categories(self, topic_dist: dict[str, int]) -> dict:
        total = sum(topic_dist.values()) or 1
        distribution = {
            topic: {"count": count, "share": round(count / total * 100, 1)}
            for topic, count in list(topic_dist.items())[:15]
        }

        top = list(topic_dist.items())[:5]
        emerging = [
            topic for topic, count in top
            if count >= 3
        ]

        return {
            "total_posts_analyzed": total,
            "unique_categories": len(topic_dist),
            "top_categories": [{"topic": t, "count": c} for t, c in top],
            "category_distribution": distribution,
            "hot_topics": emerging,
        }

    def build_report_data(self, trending: list[dict], velocity: list[dict],
                          category_analysis: dict, period: str = "day") -> dict:
        return {
            "period": period,
            "generated_at": datetime_utc_now(),
            "summary": {
                "total_trending": len(trending),
                "avg_trend_score": (
                    round(sum(p.get("trend_score", 0) for p in trending) / len(trending), 1)
                    if trending else 0
                ),
                "highest_score": trending[0]["trend_score"] if trending else 0,
                "top_category": (
                    category_analysis["top_categories"][0]["topic"]
                    if category_analysis["top_categories"] else "N/A"
                ),
            },
            "trending_products": trending,
            "top_velocity": velocity[:5],
            "category_analysis": category_analysis,
            "highlights": self._extract_highlights(trending),
        }

    def _extract_highlights(self, trending: list[dict]) -> list[str]:
        highlights = []
        if not trending:
            return ["No trending products found in this period."]

        top = trending[0]
        highlights.append(
            f"🏆 Top product: {top['name']} ({top.get('trend_score', 0)} pts)"
        )

        categories = Counter()
        for p in trending:
            for t in p.get("topics_raw", p.get("topics", [])):
                categories[t] += 1
        if categories:
            top_cat = categories.most_common(1)[0][0]
            highlights.append(f"📈 Most active category: {top_cat}")

        fastest = max(trending, key=lambda x: x.get("vote_delta", 0), default=None)
        if fastest and fastest.get("vote_delta", 0) > 0:
            highlights.append(
                f"🚀 Fastest rising: {fastest['name']} (+{fastest['vote_delta']} votes)"
            )

        return highlights


def datetime_utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
