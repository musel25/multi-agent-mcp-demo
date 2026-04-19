#!/usr/bin/env python3
"""
Multi-Agent MCP Server
Shared state for two Claude agents communicating through domain + message-bus tools.
Runs as a persistent SSE server on http://localhost:8000.
"""

import json
import uuid
from datetime import datetime
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import HTMLResponse

mcp = FastMCP("multi-agent-server")
mcp.settings.host = "0.0.0.0"
mcp.settings.port = 8000

# ── In-memory state ────────────────────────────────────────────────────────────

services = {
    "svc_001": {"name": "Data Analysis Service", "price": 150.0, "available": True},
    "svc_002": {"name": "Translation Service",   "price":  75.0, "available": False},
}

transactions: dict[str, dict] = {}
mailboxes:    dict[str, list] = {}   # agent_name -> [{id, from, content, read}]


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ── Domain tools ───────────────────────────────────────────────────────────────

@mcp.tool()
def check_availability(service_id: str) -> dict:
    """Check whether a service exists and is available, and return its price."""
    log(f"check_availability(service_id={service_id!r})")
    if service_id not in services:
        return {"available": False, "error": "Service not found"}
    svc = services[service_id]
    return {"available": svc["available"], "name": svc["name"], "price": svc["price"]}


@mcp.tool()
def send_payment(amount: float, destination: str) -> dict:
    """Record a payment destined for `destination`. Returns a transaction_id."""
    log(f"send_payment(amount={amount}, destination={destination!r})")
    txn_id = f"txn_{uuid.uuid4().hex[:8]}"
    transactions[txn_id] = {
        "amount":      amount,
        "destination": destination,
        "confirmed":   False,
        "timestamp":   datetime.now().isoformat(),
    }
    return {"transaction_id": txn_id, "status": "pending", "amount": amount}


@mcp.tool()
def confirm_receipt(transaction_id: str) -> dict:
    """Mark a transaction as confirmed (receipt acknowledged)."""
    log(f"confirm_receipt(transaction_id={transaction_id!r})")
    if transaction_id not in transactions:
        return {"success": False, "error": "Transaction not found"}
    transactions[transaction_id]["confirmed"] = True
    return {"success": True, "transaction_id": transaction_id, "status": "confirmed"}


# ── Message-bus tools ──────────────────────────────────────────────────────────

@mcp.tool()
def post_message(from_agent: str, to_agent: str, content: str) -> dict:
    """Drop a message into `to_agent`'s inbox."""
    preview = content[:70] + ("…" if len(content) > 70 else "")
    log(f"post_message(from={from_agent!r} -> to={to_agent!r}): {preview!r}")
    mailboxes.setdefault(to_agent, []).append({
        "id":        uuid.uuid4().hex[:8],
        "from":      from_agent,
        "content":   content,
        "read":      False,
        "timestamp": datetime.now().isoformat(),
    })
    return {"success": True, "message_id": mailboxes[to_agent][-1]["id"]}


@mcp.tool()
def poll_messages(for_agent: str) -> dict:
    """Return all unread messages for `for_agent` and mark them as read."""
    log(f"poll_messages(for_agent={for_agent!r})")
    inbox  = mailboxes.get(for_agent, [])
    unread = [m for m in inbox if not m["read"]]
    for m in unread:
        m["read"] = True
    log(f"  -> {len(unread)} unread message(s)")
    return {
        "messages": [
            {"id": m["id"], "from": m["from"], "content": m["content"]}
            for m in unread
        ]
    }


# ── Status page ────────────────────────────────────────────────────────────────

@mcp.custom_route("/", methods=["GET"])
async def status_page(request: Request) -> HTMLResponse:
    txn_confirmed = sum(1 for t in transactions.values() if t["confirmed"])
    rows = ""
    for name, msgs in mailboxes.items():
        unread = sum(1 for m in msgs if not m["read"])
        rows += f"<tr><td>{name}</td><td>{len(msgs)}</td><td>{unread}</td></tr>"
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Multi-Agent MCP Server</title>
<meta http-equiv="refresh" content="3">
<style>
  body{{font-family:monospace;padding:2rem;background:#111;color:#eee}}
  h1{{color:#7ef;margin-bottom:.5rem}}
  .badge{{display:inline-block;padding:.2rem .6rem;border-radius:4px;background:#1a3a1a;color:#4f4}}
  table{{border-collapse:collapse;margin-top:1rem;width:100%}}
  th,td{{border:1px solid #333;padding:.4rem .8rem;text-align:left}}
  th{{background:#222}}
  .dim{{color:#888;font-size:.85rem}}
</style></head><body>
<h1>Multi-Agent MCP Server</h1>
<p class="badge">RUNNING</p>&nbsp;
<span class="dim">SSE endpoint: <code>http://localhost:8000/sse</code> &bull; refreshes every 3s</span>
<h3>State</h3>
<table>
  <tr><th>Metric</th><th>Value</th></tr>
  <tr><td>Services</td><td>{len(services)}</td></tr>
  <tr><td>Transactions (total / confirmed)</td><td>{len(transactions)} / {txn_confirmed}</td></tr>
  <tr><td>Active mailboxes</td><td>{len(mailboxes)}</td></tr>
</table>
<h3>Mailboxes</h3>
{"<table><tr><th>Agent</th><th>Total msgs</th><th>Unread</th></tr>" + rows + "</table>" if rows else "<p class='dim'>No messages yet.</p>"}
<h3>Transactions</h3>
{"<pre>" + json.dumps(transactions, indent=2) + "</pre>" if transactions else "<p class='dim'>No transactions yet.</p>"}
</body></html>"""
    return HTMLResponse(html)


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log("Multi-agent MCP server starting on http://localhost:8000")
    mcp.run(transport="sse")
