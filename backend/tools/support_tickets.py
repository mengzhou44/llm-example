import httpx

TOOL_DEFINITION = {
    "name": "get_support_ticket",
    "description": (
        "Fetch a support ticket by ID from the external support system. "
        "Returns the ticket's title, status, priority, description, and any resolution notes. "
        "Use this when the user asks about a specific support ticket by ID."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ticket_id": {
                "type": "string",
                "description": "The numeric support ticket ID, e.g. '1001' or '1002'",
            }
        },
        "required": ["ticket_id"],
    },
}


async def fetch_support_ticket(ticket_id: str) -> str:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"http://localhost:4000/mock/tickets/{ticket_id}", timeout=5.0
            )
            if resp.status_code == 404:
                return f"Ticket {ticket_id} was not found in the support system."
            resp.raise_for_status()
            t = resp.json()
            lines = [
                f"Ticket #{t['id']}: {t['title']}",
                f"Status: {t['status']} | Priority: {t['priority']} | Created: {t['created']}",
                f"Description: {t['description']}",
            ]
            if t.get("resolution"):
                lines.append(f"Resolution: {t['resolution']}")
            return "\n".join(lines)
    except Exception as e:
        return f"Error fetching ticket {ticket_id}: {e}"
