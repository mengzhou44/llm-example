from tools.support_tickets import (
    LIST_TOOL_DEFINITION,
    TOOL_DEFINITION,
    UPDATE_TOOL_DEFINITION,
    fetch_support_ticket,
    list_support_tickets,
    update_ticket_status,
)

TOOLS = [TOOL_DEFINITION, LIST_TOOL_DEFINITION, UPDATE_TOOL_DEFINITION]


async def execute_tool(name: str, tool_input: dict) -> str:
    if name == "get_support_ticket":
        return await fetch_support_ticket(tool_input["ticket_id"])
    if name == "list_support_tickets":
        return await list_support_tickets(tool_input.get("status"))
    if name == "update_ticket_status":
        return await update_ticket_status(
            tool_input["ticket_id"],
            tool_input["status"],
            tool_input.get("resolution"),
        )
    return f"Unknown tool: {name}"
