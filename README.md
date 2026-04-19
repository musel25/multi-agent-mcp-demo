# Multi-Agent MCP Demo

Two Claude Code agents (Agent A and Agent B) coordinate autonomously through a shared MCP server — no orchestrator, no human input after startup. Agent A purchases a service, Agent B processes the payment, and Agent A confirms receipt.

```
Terminal 1: MCP server (shared state + live status page)
Terminal 2: Agent A (buyer)
Terminal 3: Agent B (service provider)
```

---

## Install

```bash
# Python dependencies (uses uv — install from https://docs.astral.sh/uv if needed)
uv add "mcp[cli]"

# Claude Code CLI (if not already installed)
npm install -g @anthropic-ai/claude-code
```

> Requires Python 3.10+ and Node 18+.

---

## Step 1 — Start the MCP server (Terminal 1)

```bash
cd /path/to/multi-agent-mcp-demo
uv run python mcp_server.py
```

You should see:

```
[HH:MM:SS] Multi-agent MCP server starting on http://localhost:8000
INFO:     Started server process [...]
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Open **http://localhost:8000** in your browser — you'll see a live status dashboard that auto-refreshes every 3 seconds.  
The actual MCP endpoint used by agents is `http://localhost:8000/sse`.

Leave this terminal running. Every tool call from both agents will be logged here in real time.

---

## Step 2 — Register the MCP server with Claude Code (run once)

In any terminal (server must be running):

```bash
claude mcp add --transport sse multi-agent-server http://localhost:8000/sse
```

This persists to your Claude Code config — you only need to do it once per machine.

Verify it was added:

```bash
claude mcp list
```

You should see `multi-agent-server` with the SSE URL.

---

## Step 3 — Start Agent B first (Terminal 2)

Open a new terminal, navigate to the project directory, start a Claude Code session:

```bash
cd /path/to/multi-agent-mcp-demo
claude
```

When Claude Code is ready, paste the entire contents of `agent_b_prompt.txt` as your first message and press Enter.

Agent B will immediately begin polling for messages from Agent A.

---

## Step 4 — Start Agent A (Terminal 3)

Open another new terminal:

```bash
cd /path/to/multi-agent-mcp-demo
claude
```

Paste the entire contents of `agent_a_prompt.txt` and press Enter.

Agent A will check service availability, post a purchase request, and wait for Agent B's reply.

---

## What a successful run looks like

**Terminal 1 (server log):**
```
[10:01:02] check_availability(service_id='svc_001')
[10:01:02] post_message(from='agent_a' -> to='agent_b'): 'REQUEST svc_001: I would like to purchase…'
[10:01:04] poll_messages(for_agent='agent_b')
[10:01:04]   -> 1 unread message(s)
[10:01:04] check_availability(service_id='svc_001')
[10:01:04] send_payment(amount=150.0, destination='agent_b')
[10:01:05] post_message(from='agent_b' -> to='agent_a'): 'PAYMENT PROCESSED: Service svc_001 approved…'
[10:01:07] poll_messages(for_agent='agent_a')
[10:01:07]   -> 1 unread message(s)
[10:01:07] confirm_receipt(transaction_id='txn_a1b2c3d4')
[10:01:08] post_message(from='agent_a' -> to='agent_b'): 'CONFIRMED: Receipt acknowledged…'
[10:01:09] poll_messages(for_agent='agent_b')
[10:01:09]   -> 1 unread message(s)
```

**Terminal 2 (Agent B):**
```
Workflow complete.
- Service fulfilled: Data Analysis Service
- Amount charged: $150.00
- Transaction ID: txn_a1b2c3d4
- Agent A confirmed: yes
```

**Terminal 3 (Agent A):**
```
Workflow complete.
- Service purchased: Data Analysis Service
- Amount: $150.00
- Transaction ID: txn_a1b2c3d4
- Confirmed: yes
```

---

## Troubleshooting

**`mcp.run()` doesn't accept `host`/`port` kwargs:**
Set environment variables instead before starting the server:
```bash
FASTMCP_HOST=0.0.0.0 FASTMCP_PORT=8000 uv run python mcp_server.py
```

**Claude Code can't reach the MCP server:**
Make sure the server is running *before* starting any agent session. The SSE connection is established at session start. The MCP endpoint is `/sse`, not `/` — visiting `/` in a browser shows the status dashboard, not MCP traffic.

**Agent gets stuck polling:**
The prompts allow up to 30–40 polls. If an agent times out, check Terminal 1 to see which tool calls arrived. Usually this means one agent started before the other was ready — just restart both agent sessions.

**`ImportError: cannot import name 'FastMCP'`:**
Upgrade the SDK:
```bash
uv add --upgrade "mcp[cli]"
```
