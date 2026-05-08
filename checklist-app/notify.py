import os
import json
import requests
from datetime import date

GIST_ID       = os.environ["CHECKLIST_GIST_ID"]
GITHUB_TOKEN  = os.environ["CHECKLIST_GITHUB_TOKEN"]
TG_TOKEN      = os.environ["TELEGRAM_BOT_TOKEN"]
TG_CHAT_ID    = os.environ["TELEGRAM_CHAT_ID"]

r = requests.get(
    f"https://api.github.com/gists/{GIST_ID}",
    headers={"Authorization": f"token {GITHUB_TOKEN}"},
    timeout=10,
)
r.raise_for_status()
lists = json.loads(r.json()["files"]["checklist.json"]["content"])

today = date.today()
today_str = today.strftime("%a, %-d %b %Y")
priority_icon = {"high": "🔴", "med": "🟡", "low": "🔵"}

lines = [f"📋 *Checklist Digest — {today_str}*\n"]
total_pending = 0

for lst in lists:
    pending = [t for t in lst["tasks"] if not t["done"]]
    if not pending:
        continue
    done_count = sum(1 for t in lst["tasks"] if t["done"])
    lines.append(f"*{lst['title']}* — {done_count}/{len(lst['tasks'])} done")
    for t in pending:
        icon = priority_icon.get(t.get("priority", "med"), "⚪")
        due = t.get("dueDate", "")
        due_label = f" · due {due}" if due else ""
        overdue = " ⚠️" if due and due < str(today) else ""
        lines.append(f"  {icon} {t['text']}{due_label}{overdue}")
    total_pending += len(pending)
    lines.append("")

if total_pending == 0:
    lines.append("✅ All tasks complete — nothing pending!")
else:
    lines.append(f"_{total_pending} task{'s' if total_pending > 1 else ''} pending_")

message = "\n".join(lines)

resp = requests.post(
    f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
    json={"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "Markdown"},
    timeout=10,
)
resp.raise_for_status()
print(f"Sent digest: {total_pending} pending tasks")
