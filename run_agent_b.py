#!/usr/bin/env python3
"""
Agent B — seller.

Polls for a purchase request from Agent A, verifies service availability,
processes the payment, notifies Agent A with the transaction ID,
then waits for confirmation.

Usage:
    uv run python run_agent_b.py
"""

import asyncio
import json

from mcp import ClientSession
from mcp.client.sse import sse_client

SERVER = "http://localhost:8000/sse"
MAX_POLLS = 40


async def call(session: ClientSession, tool: str, **kwargs) -> dict:
    result = await session.call_tool(tool, arguments=kwargs)
    return json.loads(result.content[0].text)


async def main() -> None:
    async with sse_client(SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("[B] Online — waiting for Agent A's request…")

            # 1. Poll for Agent A's purchase request
            for i in range(1, MAX_POLLS + 1):
                poll = await call(session, "poll_messages", for_agent="agent_b")
                request = next(
                    (m for m in poll.get("messages", [])
                     if m.get("from") == "agent_a" and "REQUEST svc_001" in m.get("content", "")),
                    None,
                )
                if request:
                    print(f"[B] Request received: {request['content'][:80]}…")
                    break
                print(f"[B] poll {i}/{MAX_POLLS} — no request yet…")
                await asyncio.sleep(1)
            else:
                print("[B] No request received — aborting.")
                return

            # 2. Verify service on the server (authoritative price)
            svc = await call(session, "check_availability", service_id="svc_001")
            if not svc.get("available"):
                print("[B] svc_001 not available — aborting.")
                return
            price = svc["price"]

            # 3. Process payment
            payment = await call(session, "send_payment", amount=price, destination="agent_b")
            txn_id = payment["transaction_id"]
            print(f"[B] Payment processed: {txn_id} (${price})")

            # 4. Notify Agent A
            await call(
                session, "post_message",
                from_agent="agent_b", to_agent="agent_a",
                content=(
                    f"PAYMENT PROCESSED: Service svc_001 approved. "
                    f"Payment of ${price} recorded. Transaction ID: {txn_id}. "
                    "Please call confirm_receipt with this transaction ID."
                ),
            )
            print("[B] Transaction ID sent to agent_a.")

            # 5. Wait for Agent A's confirmation
            confirmed = False
            for i in range(1, 31):
                poll = await call(session, "poll_messages", for_agent="agent_b")
                if any("CONFIRMED" in m.get("content", "") and m.get("from") == "agent_a"
                       for m in poll.get("messages", [])):
                    confirmed = True
                    break
                print(f"[B] poll {i}/30 — waiting for confirmation…")
                await asyncio.sleep(2)

            # 6. Summary
            print(f"\n{'─'*45}")
            print("  Agent B — workflow complete")
            print(f"{'─'*45}")
            print(f"  Service     : {svc['name']}")
            print(f"  Amount      : ${price}")
            print(f"  Transaction : {txn_id}")
            print(f"  Confirmed   : {'yes' if confirmed else 'no (timed out)'}")
            print(f"{'─'*45}")


if __name__ == "__main__":
    asyncio.run(main())
