import httpx

LIST_TOOL_DEFINITION = {
    "name": "list_support_tickets",
    "description": (
        "List support tickets from the external support system, optionally filtered by status. "
        "Use this when the user asks to see all tickets, open tickets, resolved tickets, etc."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "Optional status filter: 'Open', 'In Progress', or 'Resolved'. Omit to return all tickets.",
                "enum": ["Open", "In Progress", "Resolved"],
            }
        },
        "required": [],
    },
}

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


async def list_support_tickets(status: str | None = None) -> str:
    try:
        params = {"status": status} if status else {}
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "http://localhost:4000/mock/tickets", params=params, timeout=5.0
            )
            resp.raise_for_status()
            tickets = resp.json()
        if not tickets:
            label = f" with status '{status}'" if status else ""
            return f"No tickets found{label}."
        lines = []
        for t in tickets:
            line = f"#{t['id']} [{t['status']}] {t['title']} (Priority: {t['priority']}, Created: {t['created']})"
            lines.append(line)
        header = f"Tickets (filtered by status='{status}'):" if status else "All tickets:"
        return header + "\n" + "\n".join(lines)
    except Exception as e:
        return f"Error listing tickets: {e}"


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
