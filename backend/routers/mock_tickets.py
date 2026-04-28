from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/mock")

_TICKETS = {
    "1001": {
        "id": "1001",
        "title": "Login page not loading on Safari",
        "status": "Open",
        "priority": "High",
        "created": "2026-04-20",
        "description": "Users report the login page fails to load on Safari 17+. Blank white screen after navigating to /login.",
        "resolution": None,
    },
    "1002": {
        "id": "1002",
        "title": "Export to CSV produces empty file",
        "status": "Resolved",
        "priority": "Medium",
        "created": "2026-04-15",
        "description": "CSV export feature returns an empty file when more than 1000 rows are selected.",
        "resolution": "Fixed in v2.3.1 — increased export row limit and fixed streaming write issue.",
    },
    "1003": {
        "id": "1003",
        "title": "Email notifications delayed by 2–3 hours",
        "status": "In Progress",
        "priority": "High",
        "created": "2026-04-22",
        "description": "Users are receiving email notifications 2–3 hours after the triggering event. Affects order confirmations and password reset emails.",
        "resolution": None,
    },
    "1004": {
        "id": "1004",
        "title": "Dashboard charts not rendering on mobile",
        "status": "Open",
        "priority": "Low",
        "created": "2026-04-24",
        "description": "Bar and line charts in the dashboard are blank on mobile devices with screen width < 768px. Desktop is unaffected.",
        "resolution": None,
    },
    "1005": {
        "id": "1005",
        "title": "Search returning no results for accented characters",
        "status": "Resolved",
        "priority": "Medium",
        "created": "2026-04-10",
        "description": "Full-text search fails to match results when query contains accented characters (e.g. café, résumé).",
        "resolution": "Fixed by normalizing input and index to NFC unicode form before comparison.",
    },
}


@router.get("/tickets")
async def list_tickets(status: str | None = None):
    tickets = list(_TICKETS.values())
    if status:
        tickets = [t for t in tickets if t["status"].lower() == status.lower()]
    return tickets


@router.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: str):
    ticket = _TICKETS.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    return ticket
