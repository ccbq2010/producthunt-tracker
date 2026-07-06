# Product Hunt Trend Tracker

Track trending products on Product Hunt. Generate daily/weekly reports. Push via email or webhook.

## Features

- **Multi-topic aggregation** — fetches posts from multiple PH topics, deduplicates automatically
- **Trend scoring** — composite score based on total engagement + momentum (vote/comment deltas)
- **Velocity tracking** — identifies fastest-growing products by votes/day
- **Category analysis** — shows which categories are heating up
- **Multiple outputs** — Markdown reports, HTML, email (SMTP), Slack/Discord webhooks
- **SQLite storage** — zero-config persistence, automatic snapshots for historical comparison
- **Scheduled** — cron-friendly CLI for daily/weekly automation

## Quick Start

```bash
# 1. Copy config and add your token
cp config/settings.example.yml config/settings.yml
# Edit config/settings.yml — set your Product Hunt API token

# 2. Fetch latest data
python main.py fetch

# 3. Generate and print a daily report
python main.py report --print

# 4. Or do both at once
python main.py run --print
```

## Getting a Product Hunt Token

1. Go to https://www.producthunt.com/v2/oauth/applications
2. Create a new application
3. Copy the API token into `config/settings.yml` under `token`

## Commands

| Command | Description |
|---------|-------------|
| `python main.py fetch` | Fetch latest posts and update database |
| `python main.py report` | Generate report from stored data |
| `python main.py run` | Fetch + report in one step |

### Options

- `-p, --period day|week` — Report period (default: from config)
- `-o, --output FILE` — Save report to specific file
- `--print` — Print report to stdout
- `-c, --config PATH` — Config file path
- `-v, --verbose` — Debug logging

## Automation (Cron)

Daily at 9: UTC:

```
0 9 * * * cd /path/to/producthunt-tracker && python main.py run -p day
```

Weekly on Monday:

```
0 9 * * 1 cd /path/to/producthunt-tracker && python main.py run -p week
```

## Project Structure

```
producthunt-tracker/
├── config/
│   ├── settings.example.yml
│   └── settings.yml            # Your local config (gitignored)
├── src/
│   ├── fetcher.py              # PH GraphQL API client
│   ├── storage.py              # SQLite persistence + trends queries
│   ├── analyzer.py             # Trend scoring + category analysis
│   ├── reporter.py             # Markdown/HTML report generation
│   └── notifier.py             # Email + webhook delivery
├── data/
│   ├── producthunt.db          # SQLite database
│   └── reports/                # Generated reports
├── main.py                     # CLI entry point
└── requirements.txt
```

## Trend Score Formula

```
trend_score = (votes + comments * 2) + 0.5 * (vote_delta + comment_delta * 1.5)
```

Where `vote_delta` / `comment_delta` are changes since the last capture within the period window.
