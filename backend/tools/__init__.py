from tools.support_tickets import (
    LIST_TOOL_DEFINITION,
    TOOL_DEFINITION,
    fetch_support_ticket,
    list_support_tickets,
)

TOOLS = [TOOL_DEFINITION, LIST_TOOL_DEFINITION]


async def execute_tool(name: str, tool_input: dict) -> str:
    if name == "get_support_ticket":
        return await fetch_support_ticket(tool_input["ticket_id"])
    if name == "list_support_tickets":
        return await list_support_tickets(tool_input.get("status"))
    return f"Unknown tool: {name}"
