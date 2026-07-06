import json
import logging
import os
import smtplib
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from string import Template

logger = logging.getLogger(__name__)

EMAIL_HTML_TEMPLATE = Template("""
<html>
<body style="font-family: -apple-system, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
<h1 style="color: #da552f;">Product Hunt Trends — $period</h1>
<p style="color: #999;">Generated: $generated_at</p>

<h2>Highlights</h2>
<ul>
$highlights
</ul>

<h2>Top Trending</h2>
$products

<p style="color: #999; font-size: 12px; margin-top: 30px;">— Sent by PH Trend Tracker</p>
</body>
</html>
""")


class Notifier:
    def __init__(self, config: dict):
        self.config = config
        self.file_config = config.get("notify", {}).get("file", {})
        self.email_config = config.get("notify", {}).get("email", {})
        self.webhook_config = config.get("notify", {}).get("webhook", {})

    def send(self, data: dict, report_md: str, report_path: str | None = None):
        if self.file_config.get("enabled", True):
            self._save_to_file(report_md, data.get("period", "day"))

        if self.email_config.get("enabled", False):
            self._send_email(data, report_md)

        if self.webhook_config.get("enabled", False):
            self._send_webhook(data)

    def _save_to_file(self, md: str, period: str):
        output_dir = self.file_config.get("path", "data/reports/")
        os.makedirs(output_dir, exist_ok=True)
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        filename = f"latest_{period}.md"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md)
        logger.info(f"Saved latest report to {filepath}")

    def _send_email(self, data: dict, md: str):
        cfg = self.email_config
        highlights = data.get("highlights", [])
        trending = data.get("trending_products", [])[:5]

        highlights_html = "\n".join(f"<li>{h}</li>" for h in highlights)

        products_html = ""
        for p in trending:
            products_html += f"""
            <div style="margin-bottom: 16px; border-left: 3px solid #da552f; padding-left: 12px;">
                <strong>{p.get('name', '')}</strong><br>
                <span style="color: #666;">{p.get('tagline', '')}</span><br>
                <small>Score: {p.get('trend_score', 0)} | Votes: +{p.get('vote_delta', 0)}</small>
            </div>
            """

        html = EMAIL_HTML_TEMPLATE.substitute(
            period=data.get("period", "day").capitalize(),
            generated_at=data.get("generated_at", ""),
            highlights=highlights_html,
            products=products_html,
        )

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Product Hunt Trends — {data.get('period', 'day').capitalize()}"
        msg["From"] = cfg.get("from_addr", "")
        msg["To"] = ", ".join(cfg.get("to_addrs", []))
        msg.attach(MIMEText(md, "plain"))
        msg.attach(MIMEText(html, "html"))

        try:
            if cfg.get("use_tls", True):
                server = smtplib.SMTP(cfg["smtp_host"], cfg.get("smtp_port", 587))
                server.starttls()
            else:
                server = smtplib.SMTP(cfg["smtp_host"], cfg.get("smtp_port", 25))
            if cfg.get("username"):
                server.login(cfg["username"], cfg["password"])
            server.send_message(msg)
            server.quit()
            logger.info(f"Email sent to {cfg.get('to_addrs', [])}")
        except Exception as e:
            logger.error(f"Failed to send email: {e}")

    def _send_webhook(self, data: dict):
        cfg = self.webhook_config
        trending = data.get("trending_products", [])[:5]

        summary_parts = [
            f"*{data.get('period', 'day').capitalize()} Product Hunt Trends*",
            "",
        ]
        for p in trending:
            summary_parts.append(
                f"• *{p.get('name', '')}* — {p.get('tagline', '')}\n"
                f"  Score: {p.get('trend_score', 0)} | Votes: +{p.get('vote_delta', 0)}"
            )

        payload = {"text": "\n".join(summary_parts)}

        try:
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                cfg["url"],
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info(f"Webhook sent, status: {resp.status}")
        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")
