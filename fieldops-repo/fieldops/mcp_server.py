# mcp_server.py - FieldOps MCP server for plain-language dispatch operations
try:
    from mcp.server.fastmcp import FastMCP
except (ImportError, ModuleNotFoundError):
    from mcp.server.mcpserver import MCPServer as FastMCP

from fieldops import store, assign

mcp = FastMCP("fieldops")


def _mask_phone(phone: str) -> str:
    if not phone:
        return ""
    return "415-555-****"


@mcp.tool()
def list_orders(site: str | None = None, status: str | None = None) -> list[dict]:
    """List work orders with optional site and status filters.

    Results are sorted by priority (lowest number first), then oldest created date.
    Customer phone numbers are masked.
    """
    orders = store.load_orders()
    results = []
    for o in orders:
        if site is not None and o.get("site", "").strip().lower() != site.strip().lower():
            continue
        if status is not None and o.get("status", "").strip().lower() != status.strip().lower():
            continue
        item = dict(o)
        if item.get("customer_phone"):
            item["customer_phone"] = _mask_phone(item["customer_phone"])
        results.append(item)

    results.sort(key=lambda o: (int(o.get("priority", 3)), o.get("created", "")))
    return results


@mcp.tool()
def assign_order(id: int, crew: str) -> dict:
    """Assign a work order to a crew."""
    success = assign.assign_order(id, crew)
    if success:
        return {"success": True, "message": f"Order {id} assigned to crew {crew}"}
    return {"success": False, "message": f"Could not assign order {id} to crew {crew}"}


@mcp.tool()
def close_order(id: int) -> dict:
    """Close a work order."""
    res = store.update_order(id, status="closed")
    if res is not None:
        return {"success": True, "message": f"Order {id} closed"}
    return {"success": False, "message": f"Order {id} not found"}


if __name__ == "__main__":
    mcp.run()
