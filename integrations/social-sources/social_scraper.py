"""
Social sources tracker (GitHub + Slack), kept separate from company blogs.
Stores items in the Supabase table "social_items".
Inserts new items and updates ones whose content changed.

Env vars:
  SUPABASE_URL, SUPABASE_KEY   (service_role key)
  GITHUB_TOKEN                 optional, raises GitHub rate limits
  SLACK_BOT_TOKEN              optional, xoxb-... token of your Slack app
  SLACK_CHANNEL_IDS            optional, comma-separated channel IDs (C0123ABCD,...)
"""
import os
import hashlib
import datetime as dt
import requests
from supabase import create_client

GITHUB_ORGS = ["Netflix", "cloudflare", "spotify", "discord"]
WATCH_REPOS = [  # releases of these repos are tracked
    "Netflix/chaosmonkey",
    "chaos-mesh/chaos-mesh",
    "litmuschaos/litmus",
]


def sha(*parts):
    return hashlib.sha256("|".join(p or "" for p in parts).encode("utf-8")).hexdigest()


def github_items():
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    items = []

    for org in GITHUB_ORGS:
        r = requests.get(f"https://api.github.com/orgs/{org}/repos",
                         params={"sort": "pushed", "per_page": 10},
                         headers=headers, timeout=30)
        if not r.ok:
            print(f"[!] GitHub org {org}: HTTP {r.status_code}")
            continue
        for repo in r.json():
            desc = repo.get("description") or ""
            items.append({
                "source": "github", "source_ref": org,
                "external_id": repo["html_url"],
                "title": repo["full_name"], "link": repo["html_url"],
                "body": desc, "author": org,
                "posted_at": repo.get("pushed_at"),
                # pushed_at in the hash: updates whenever the repo gets new commits
                "content_hash": sha(desc, repo.get("pushed_at")),
            })

    for repo in WATCH_REPOS:
        r = requests.get(f"https://api.github.com/repos/{repo}/releases",
                         params={"per_page": 5}, headers=headers, timeout=30)
        if not r.ok:
            print(f"[!] GitHub releases {repo}: HTTP {r.status_code}")
            continue
        for rel in r.json():
            name = rel.get("name") or rel.get("tag_name") or ""
            body = (rel.get("body") or "")[:2000]
            items.append({
                "source": "github", "source_ref": repo,
                "external_id": rel["html_url"],
                "title": f"{repo} {name}", "link": rel["html_url"],
                "body": body, "author": repo,
                "posted_at": rel.get("published_at"),
                "content_hash": sha(name, body),
            })
    return items


def slack_items():
    token = os.environ.get("SLACK_BOT_TOKEN")
    channels = [c.strip() for c in os.environ.get("SLACK_CHANNEL_IDS", "").split(",") if c.strip()]
    if not token or not channels:
        print("Slack skipped (no SLACK_BOT_TOKEN / SLACK_CHANNEL_IDS)")
        return []
    headers = {"Authorization": f"Bearer {token}"}
    items = []

    def permalink(ch, ts):
        r = requests.get("https://slack.com/api/chat.getPermalink",
                         params={"channel": ch, "message_ts": ts},
                         headers=headers, timeout=30).json()
        return r.get("permalink")

    for ch in channels:
        r = requests.get("https://slack.com/api/conversations.history",
                         params={"channel": ch, "limit": 50},
                         headers=headers, timeout=30).json()
        if not r.get("ok"):
            print(f"[!] Slack {ch}: {r.get('error')}")
            continue
        for m in r["messages"]:
            text = m.get("text", "")
            if m.get("subtype") or not text:  # skip joins, bot noise, empty
                continue
            ts = m["ts"]
            items.append({
                "source": "slack", "source_ref": ch,
                "external_id": f"{ch}:{ts}",
                "title": text[:80], "link": None,
                "resolve_link": lambda ch=ch, ts=ts: permalink(ch, ts),  # only called for new/changed
                "body": text[:2000], "author": m.get("user"),
                "posted_at": dt.datetime.fromtimestamp(float(ts), dt.timezone.utc).isoformat(),
                "content_hash": sha(text),
            })
    return items


def save(sb, items, label):
    if not items:
        print(f"{label}: nothing to check")
        return
    now = dt.datetime.now(dt.timezone.utc).isoformat()

    known = {}
    ids = [i["external_id"] for i in items]
    for start in range(0, len(ids), 100):
        chunk = ids[start:start + 100]
        data = sb.table("social_items").select("external_id,content_hash") \
                 .in_("external_id", chunk).execute().data
        known.update({r["external_id"]: r["content_hash"] for r in data})

    rows = []
    for i in items:
        if known.get(i["external_id"]) == i["content_hash"]:
            continue  # unchanged
        row = {k: v for k, v in i.items() if k != "resolve_link"}
        if row.get("link") is None and i.get("resolve_link"):
            row["link"] = i["resolve_link"]()
        row["updated_at"] = now
        rows.append(row)

    if rows:
        sb.table("social_items").upsert(rows, on_conflict="external_id").execute()
    print(f"{label}: {len(rows)} new/changed of {len(items)} checked")


def main():
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    save(sb, github_items(), "GitHub")
    save(sb, slack_items(), "Slack")


if __name__ == "__main__":
    main()
