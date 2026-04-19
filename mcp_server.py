#!/usr/bin/env python3
"""
Multi-Agent MCP Server
Shared state for two Claude agents communicating through domain + message-bus tools.
Runs as a persistent SSE server on http://localhost:8000.
"""

import uuid
from datetime import datetime
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("multi-agent-server")
mcp.settings.host = "0.0.0.0"
mcp.settings.port = 8000

# ── In-memory state ──────────────────────────────────────────────────

services = {
    "svc_001": {"name": "Data Analysis Service", "price": 150.0, "available": True},
    "svc_002": {"name": "Translation Service",   "price":  75.0, "available": False},
}

transactions: dict[str, dict] = {}
mailboxes:    dict[str, list] = {}   # agent_name -> [{id, from, content, read}]


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ── Domain tools ───────────────────────────────────────────────────

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


# ── Message-bus tools ─────────────────────────────────────────────────

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


# ── Entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    log("Multi-agent MCP server starting on http://localhost:8000")
    mcp.run(transport="sse")
