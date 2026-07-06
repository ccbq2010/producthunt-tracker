import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class Reporter:
    def __init__(self, output_dir: str = "data/reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def render_markdown(self, data: dict) -> str:
        lines: list[str] = []

        # Header
        period = data.get("period", "day").capitalize()
        generated = data.get("generated_at", "")
        lines.append(f"# Product Hunt Trend Report — {period}")
        lines.append(f"_Generated: {generated}_")
        lines.append("")

        # Summary
        summary = data.get("summary", {})
        lines.append("## Summary")
        lines.append(f"- **Trending products:** {summary.get('total_trending', 0)}")
        lines.append(f"- **Top score:** {summary.get('highest_score', 0)}")
        lines.append(f"- **Top category:** {summary.get('top_category', 'N/A')}")
        lines.append("")

        # Highlights
        highlights = data.get("highlights", [])
        if highlights:
            lines.append("## Highlights")
            for h in highlights:
                lines.append(f"- {h}")
            lines.append("")

        # Trending products
        trending = data.get("trending_products", [])
        if trending:
            lines.append("## Trending Products")
            lines.append("")
            for i, p in enumerate(trending, 1):
                lines.append(f"### {i}. {p.get('name', 'Unknown')}")
                lines.append(f"**{p.get('tagline', '')}**")
                lines.append(f"- Score: {p.get('trend_score', 0)} | "
                             f"Votes: +{p.get('vote_delta', 0)} | "
                             f"Comments: +{p.get('comment_delta', 0)}")
                if p.get("website"):
                    lines.append(f"- [Website]({p['website']})")
                if p.get("author"):
                    lines.append(f"- By: {p['author']}")
                if p.get("topics_raw"):
                    lines.append(f"- Tags: {', '.join(p['topics_raw'][:5])}")
                lines.append("")

        # Velocity leaders
        velocity = data.get("top_velocity", [])
        if velocity:
            lines.append("## Fastest Growing")
            lines.append("")
            for v in velocity:
                lines.append(
                    f"- **{v.get('name', '')}** — "
                    f"{v.get('velocity_per_day', 0):.1f} votes/day "
                    f"(+{v.get('total_gain', 0)} total)"
                )
            lines.append("")

        # Category analysis
        cat_data = data.get("category_analysis", {})
        if cat_data.get("top_categories"):
            lines.append("## Category Breakdown")
            lines.append("")
            lines.append("| Category | Count | Share |")
            lines.append("|---|---|---|")
            for c in cat_data["top_categories"]:
                dist = cat_data.get("category_distribution", {}).get(c["topic"], {})
                lines.append(
                    f"| {c['topic']} | {c['count']} | {dist.get('share', 0)}% |"
                )
            lines.append("")

        return "\n".join(lines)

    def save_report(self, data: dict, period: str = "day") -> str:
        md = self.render_markdown(data)
        now = datetime.now(timezone.utc)
        filename = f"report_{period}_{now.strftime('%Y-%m-%d_%H%M')}.md"
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md)
        logger.info(f"Report saved to {filepath}")
        return filepath

    def render_html(self, data: dict) -> str:
        md = self.render_markdown(data)
        html_body = _md_to_html(md)
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>PH Trend Report</title>
<style>
body {{ font-family: -apple-system, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; color: #333; }}
h1 {{ color: #da552f; border-bottom: 2px solid #da552f; padding-bottom: 8px; }}
h2 {{ color: #444; margin-top: 30px; }}
h3 {{ margin-bottom: 4px; }}
a {{ color: #da552f; text-decoration: none; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #eee; }}
code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }}
</style></head><body>{html_body}</body></html>"""


def _md_to_html(md: str) -> str:
    """Minimal Markdown to HTML conversion."""
    import re

    lines = md.split("\n")
    out: list[str] = []
    in_table = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            if not in_table:
                out.append("<table><thead><tr>")
                for c in cells:
                    c = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', c)
                    c = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', c)
                    out.append(f"<th>{c}</th>")
                out.append("</tr></thead><tbody>")
                in_table = True
            else:
                out.append("<tr>")
                for c in cells:
                    c = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', c)
                    c = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', c)
                    out.append(f"<td>{c}</td>")
                out.append("</tr>")
            continue
        elif in_table:
            out.append("</tbody></table>")
            in_table = False

        if stripped.startswith("# "):
            out.append(f"<h1>{stripped[2:]}</h1>")
        elif stripped.startswith("## "):
            out.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped.startswith("### "):
            out.append(f"<h3>{stripped[4:]}</h3>")
        elif stripped.startswith("- "):
            content = stripped[2:]
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
            content = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', content)
            out.append(f"<li>{content}</li>")
        elif stripped == "":
            out.append("")
        else:
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped)
            content = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', content)
            out.append(f"<p>{content}</p>")

    if in_table:
        out.append("</tbody></table>")

    return "\n".join(out)
