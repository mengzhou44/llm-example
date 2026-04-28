from tools.support_tickets import TOOL_DEFINITION, fetch_support_ticket

TOOLS = [TOOL_DEFINITION]


async def execute_tool(name: str, tool_input: dict) -> str:
    if name == "get_support_ticket":
        return await fetch_support_ticket(tool_input["ticket_id"])
    return f"Unknown tool: {name}"
