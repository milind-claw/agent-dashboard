from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import os
import sys
from pathlib import Path

# Ensure we can import the linear agent script as a module
WORKSPACE = Path(__file__).resolve().parents[1]
LINEAR_SCRIPT = WORKSPACE / "skills" / "linear-agent" / "scripts" / "linear_agent.py"
if LINEAR_SCRIPT.exists():
    sys.path.append(str(LINEAR_SCRIPT.parent))
    try:
        import linear_agent  # type: ignore
    except Exception:  # pragma: no cover
        linear_agent = None
else:
    linear_agent = None

app = FastAPI()


def _env_flag(name: str) -> bool:
    return bool(os.getenv(name))


@app.get("/health", response_class=JSONResponse)
async def health() -> dict:
    return {
        "status": "ok",
        "linear_agent": bool(linear_agent),
    }


@app.get("/api/status", response_class=JSONResponse)
async def status() -> dict:
    """Lightweight integration status panel.

    We just check for presence of env vars / obvious files, no heavy calls.
    """
    return {
        "linear": bool(linear_agent) and _env_flag("LINEAR_API_KEY"),
        "notion": _env_flag("NOTION_API_KEY"),
        "agentmail": _env_flag("AGENTMAIL_API_KEY"),
        "obsidian_vault": str(WORKSPACE / ".." / "ObsidianValt"),
    }


@app.get("/api/linear/summary", response_class=JSONResponse)
async def linear_summary() -> dict:
    """Return grouped summary from Linear using our existing helper."""
    if linear_agent is None:
        return {"error": "linear_agent module not available"}

    client = linear_agent.LinearClient()
    issues = client.fetch_issues(team_id=os.getenv("LINEAR_TEAM_ID"), limit=50)
    buckets = {"Todo": [], "In Progress": [], "Done": []}
    for issue in issues:
        state = (issue.get("state") or {}).get("type", "").lower()
        key = "Todo"
        if state in {"started", "inprogress", "triage"}:
            key = "In Progress"
        elif state in {"completed", "done"}:
            key = "Done"
        buckets.setdefault(key, []).append(issue)
    return buckets


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    # Minimal placeholder UI for now
    return """<!DOCTYPE html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <title>Agent Dashboard</title>
    <style>
      body { font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 1.5rem; }
      .columns { display: flex; gap: 1rem; }
      .col { flex: 1; border: 1px solid #ddd; border-radius: 6px; padding: 0.5rem; }
      .col h2 { margin-top: 0; font-size: 1rem; text-transform: uppercase; letter-spacing: 0.05em; }
      .issue { border: 1px solid #eee; border-radius: 4px; padding: 0.25rem 0.5rem; margin-bottom: 0.25rem; font-size: 0.85rem; }
      .meta { font-size: 0.75rem; color: #666; }
    </style>
  </head>
  <body>
    <h1>Agent Dashboard</h1>
    <div id=\"status\">Loading...</div>
    <div id=\"integrations\" style=\"margin-bottom: 1rem; font-size: 0.85rem;\"></div>
    <div class=\"columns\" id=\"board\" style=\"display:none\">
      <div class=\"col\" data-col=\"Todo\"><h2>Todo</h2><div class=\"items\"></div></div>
      <div class=\"col\" data-col=\"In Progress\"><h2>In Progress</h2><div class=\"items\"></div></div>
      <div class=\"col\" data-col=\"Done\"><h2>Done</h2><div class=\"items\"></div></div>
    </div>
    <script>
      async function loadStatus() {
        const res = await fetch('/api/status');
        const data = await res.json();
        const el = document.getElementById('integrations');
        const parts = [];
        if (data.linear) parts.push('Linear ✅'); else parts.push('Linear ❌');
        if (data.notion) parts.push('Notion ✅'); else parts.push('Notion ❌');
        if (data.agentmail) parts.push('AgentMail ✅'); else parts.push('AgentMail ❌');
        el.textContent = 'Integrations: ' + parts.join(' · ');
      }

      async function loadBoard() {
        const res = await fetch('/api/linear/summary');
        const data = await res.json();
        const status = document.getElementById('status');
        const board = document.getElementById('board');
        if (data.error) {
          status.textContent = 'Error: ' + data.error;
          return;
        }
        status.textContent = '';
        board.style.display = 'flex';
        for (const [bucket, issues] of Object.entries(data)) {
          const col = document.querySelector(`.col[data-col="${bucket}"] .items`);
          if (!col) continue;
          col.innerHTML = '';
          for (const issue of issues) {
            const div = document.createElement('div');
            div.className = 'issue';
            div.innerHTML = `<strong>${issue.identifier}</strong> ${issue.title}<div class="meta">${issue.url}</div>`;
            col.appendChild(div);
          }
        }
      }

      Promise.all([loadStatus(), loadBoard()]).catch(err => {
        document.getElementById('status').textContent = 'Failed to load dashboard: ' + err;
      });
    </script>
  </body>
</html>
"""
