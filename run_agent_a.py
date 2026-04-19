#!/usr/bin/env python3
"""
Agent A — buyer.

Checks svc_001 availability, requests it from Agent B via the shared message bus,
waits for the transaction ID, confirms receipt, and prints a summary.

Usage:
    uv run python run_agent_a.py
"""

import asyncio
import json
import re

from mcp import ClientSession
from mcp.client.sse import sse_client

SERVER = "http://localhost:8000/sse"
MAX_POLLS = 30


async def call(session: ClientSession, tool: str, **kwargs) -> dict:
    result = await session.call_tool(tool, arguments=kwargs)
    return json.loads(result.content[0].text)


async def main() -> None:
    async with sse_client(SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. Check availability
            svc = await call(session, "check_availability", service_id="svc_001")
            if not svc.get("available"):
                print("svc_001 not available — aborting.")
                return
            print(f"[A] svc_001 available: {svc['name']} @ ${svc['price']}")

            # 2. Request service from Agent B
            await call(
                session, "post_message",
                from_agent="agent_a", to_agent="agent_b",
                content=(
                    f"REQUEST svc_001: I would like to purchase the {svc['name']}. "
                    f"Price I see is ${svc['price']}. "
                    "Please process the payment and reply with the transaction ID."
                ),
            )
            print("[A] Purchase request sent to agent_b.")

            # 3. Poll for Agent B's reply
            txn_id = None
            for i in range(1, MAX_POLLS + 1):
                poll = await call(session, "poll_messages", for_agent="agent_a")
                for msg in poll.get("messages", []):
                    if msg.get("from") == "agent_b":
                        match = re.search(r"txn_[0-9a-f]+", msg["content"])
                        if match:
                            txn_id = match.group(0)
                            break
                if txn_id:
                    break
                print(f"[A] poll {i}/{MAX_POLLS} — waiting for agent_b…")
                await asyncio.sleep(2)

            if not txn_id:
                print("[A] No transaction ID received — aborting.")
                return

            # 4. Confirm receipt
            confirm = await call(session, "confirm_receipt", transaction_id=txn_id)

            # 5. Notify Agent B
            await call(
                session, "post_message",
                from_agent="agent_a", to_agent="agent_b",
                content=f"CONFIRMED: Receipt acknowledged for transaction {txn_id}. Workflow complete. Thank you!",
            )

            # 6. Summary
            print(f"\n{'─'*45}")
            print("  Agent A — workflow complete")
            print(f"{'─'*45}")
            print(f"  Service     : {svc['name']}")
            print(f"  Amount      : ${svc['price']}")
            print(f"  Transaction : {txn_id}")
            print(f"  Status      : {confirm.get('status', 'confirmed')}")
            print(f"{'─'*45}")


if __name__ == "__main__":
    asyncio.run(main())
