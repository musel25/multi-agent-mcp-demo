# Multi-Agent MCP Demo

Two Claude Code agents (Agent A and Agent B) coordinate autonomously through a shared MCP server — no orchestrator, no human input after startup. Agent A purchases a service, Agent B processes the payment, and Agent A confirms receipt.

---

## How it works

```
┌─────────────────────────────────┐
│         mcp_server.py           │  ← shared state: services, transactions, mailboxes
│   running at localhost:8000     │
└────────────┬────────────────────┘
             │  MCP tools (SSE)
     ┌───────┴────────┐
     ▼                ▼
  Agent A          Agent B
  (buyer)        (seller)
```

The agents never talk directly — they exchange messages through `post_message` / `poll_messages` tools exposed by the MCP server. The server is the only shared state.

---

## Project structure

```
mcp_server.py        ← the MCP server (run this first, always)
agent_a_prompt.txt   ← paste into a Claude Code session to become Agent A
agent_b_prompt.txt   ← paste into a Claude Code session to become Agent B
run_agent_a.py       ← Python script version of Agent A (no Claude needed)
run_agent_b.py       ← Python script version of Agent B (no Claude needed)
```

---

## Install

```bash
# Python dependencies (uses uv — install from https://docs.astral.sh/uv if needed)
uv sync          # installs from uv.lock
# or if setting up fresh:
uv add "mcp[cli]"

# Claude Code CLI (only needed for Method 2)
npm install -g @anthropic-ai/claude-code
```

> Requires Python 3.10+ and Node 18+.

---

## Step 1 — Start the MCP server (always required)

In a dedicated terminal:

```bash
uv run python mcp_server.py
```

Expected output:
```
[HH:MM:SS] Multi-agent MCP server starting on http://localhost:8000
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Open **http://localhost:8000** in your browser — a live dashboard shows transactions and mailboxes, auto-refreshing every 3 seconds.

Leave this terminal open for the entire demo. All tool calls from both agents are logged here.

---

## Method 1 — Run with Python scripts (simpler)

No Claude Code needed. Each script connects directly to the MCP server and runs the full workflow.

**Terminal 2** — start Agent B first so it's ready to receive:
```bash
uv run python run_agent_b.py
```

**Terminal 3** — start Agent A:
```bash
uv run python run_agent_a.py
```

Agent A checks availability → posts a request → Agent B receives it → processes payment → Agent A polls for the transaction ID → confirms receipt → both print a summary.

---

## Method 2 — Run with two Claude Code instances (the real demo)

This is the intended experience: two separate AI agents talking to each other with no human in the loop.

### Register the MCP server (once per machine)

The server must be running before you do this:

```bash
claude mcp add --transport sse multi-agent-server http://localhost:8000/sse
```

Verify:
```bash
claude mcp list
# should show: multi-agent-server  http://localhost:8000/sse
```

### Start Agent B (Terminal 2)

```bash
claude
```

When the prompt appears, paste the full contents of `agent_b_prompt.txt` and press Enter. Agent B will start polling immediately.

### Start Agent A (Terminal 3)

```bash
claude
```

Paste `agent_a_prompt.txt` and press Enter. Agent A will kick off the workflow.

> **Note:** Start Agent B before Agent A. If Agent A polls and gets no reply, it retries up to 30 times — but if you start them too far apart it may time out. Just restart both sessions if that happens.

---

## What a successful run looks like

**Server log (Terminal 1):**
```
[10:01:01] check_availability(service_id='svc_001')
[10:01:02] post_message(from='agent_a' -> to='agent_b'): 'REQUEST svc_001: I would like to purchase…'
[10:01:04] poll_messages(for_agent='agent_b')
[10:01:04]   -> 1 unread message(s)
[10:01:05] check_availability(service_id='svc_001')
[10:01:05] send_payment(amount=150.0, destination='agent_b')
[10:01:06] post_message(from='agent_b' -> to='agent_a'): 'PAYMENT PROCESSED: Transaction ID: txn_…'
[10:01:08] poll_messages(for_agent='agent_a')
[10:01:08]   -> 1 unread message(s)
[10:01:09] confirm_receipt(transaction_id='txn_a1b2c3d4')
[10:01:09] post_message(from='agent_a' -> to='agent_b'): 'CONFIRMED: Receipt acknowledged…'
```

**Agent A summary:**
```
Service purchased : Data Analysis Service
Amount            : $150.0
Transaction ID    : txn_a1b2c3d4
Confirmed status  : confirmed
```

**Agent B summary:**
```
Service fulfilled : svc_001 (Data Analysis Service)
Amount charged    : $150.0
Transaction ID    : txn_a1b2c3d4
Agent A confirmed : YES
```

---

## Troubleshooting

**Agent gets stuck polling:**
Check Terminal 1 to see which tool calls arrived. Usually Agent A started before Agent B was ready. Restart both agent sessions.

**`multi-agent-server` not found by Claude Code:**
The server must be running when you run `claude mcp add`. Also make sure you're in the project directory when starting `claude` — the local `.claude/settings.json` may restrict allowed commands.

**`ImportError: cannot import name 'FastMCP'`:**
```bash
uv add --upgrade "mcp[cli]"
```

**Server port already in use:**
```bash
lsof -i :8000   # find the process
kill <PID>
```
