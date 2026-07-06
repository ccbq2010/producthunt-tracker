import json
import logging
import urllib.request
from datetime import datetime

logger = logging.getLogger(__name__)

PH_GRAPHQL = "https://api.producthunt.com/v2/api/graphql"

QUERY_POSTS = """
query($topic: String, $limit: Int!) {
    posts(order: VOTES, first: $limit, topic: $topic) {
        edges {
            node {
                id
                name
                tagline
                description
                url
                website
                votesCount
                commentsCount
                createdAt
                topics {
                    edges {
                        node { name slug }
                    }
                }
                user { name }
            }
        }
    }
}
"""

QUERY_POST_DETAIL = """
query($id: ID!) {
    post(id: $id) {
        id
        name
        tagline
        description
        url
        website
        votesCount
        commentsCount
                createdAt
                topics {
                    edges {
                        node { name slug }
                    }
                }
                user { name }
                comments(first: 5) {
            edges {
                node {
                    body
                    user { name }
                    createdAt
                }
            }
        }
    }
}
"""


class ProductHuntFetcher:
    def __init__(self, token: str, timeout: int = 15):
        self.token = token
        self.timeout = timeout

    def _request(self, query: str, variables: dict) -> dict:
        body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        req = urllib.request.Request(
            PH_GRAPHQL,
            data=body,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "ph-trend-tracker/0.1",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.error(f"PH API request failed: {e}")
            raise

    def fetch_by_topic(self, topic: str, limit: int = 20) -> list[dict]:
        resp = self._request(QUERY_POSTS, {"topic": topic, "limit": limit})
        edges = resp.get("data", {}).get("posts", {}).get("edges", [])
        results = []
        for edge in edges:
            node = edge.get("node", {})
            topics = [
                t["node"]["slug"]
                for t in node.get("topics", {}).get("edges", [])
            ]
            results.append({
                "id": node.get("id", ""),
                "name": node.get("name", ""),
                "tagline": node.get("tagline", ""),
                "description": node.get("description", "")[:1000],
                "url": node.get("url", ""),
                "website": node.get("website", ""),
                "votes_count": node.get("votesCount", 0),
                "comments_count": node.get("commentsCount", 0),
                "created_at": node.get("createdAt", ""),
                "author": node.get("user", {}).get("name", ""),
                "topics": topics,
                "source_topic": topic,
            })
        logger.info(f"Fetched {len(results)} posts for topic '{topic}'")
        return results

    def fetch_all_topics(self, topics: list[str], limit_per_topic: int = 20) -> list[dict]:
        seen: dict[str, dict] = {}
        for topic in topics:
            try:
                posts = self.fetch_by_topic(topic, limit_per_topic)
                for post in posts:
                    pid = post["id"]
                    if pid in seen:
                        if post["source_topic"] not in seen[pid]["topics"]:
                            seen[pid]["topics"].append(post["source_topic"])
                    else:
                        seen[pid] = post
            except Exception as e:
                logger.warning(f"Failed to fetch topic '{topic}': {e}")
                continue
        return list(seen.values())

    def fetch_post_detail(self, post_id: str) -> dict | None:
        resp = self._request(QUERY_POST_DETAIL, {"id": post_id})
        node = resp.get("data", {}).get("post")
        if not node:
            return None
        comments = [
            {
                "body": c["node"]["body"],
                "user": c["node"]["user"]["name"],
                "created_at": c["node"]["createdAt"],
            }
            for c in node.get("comments", {}).get("edges", [])
        ]
        return {
            "id": node["id"],
            "name": node["name"],
            "tagline": node.get("tagline", ""),
            "description": node.get("description", ""),
            "comments": comments,
        }
