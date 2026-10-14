from mcp.server.fastmcp import FastMCP
from fieldops import store, assign

mcp = FastMCP("fieldops")


@mcp.tool()
def list_orders(site: str = "", status: str = "") -> list[dict]:
    """List work orders filtered by site and status, sorted by priority (lowest number first) and oldest created date. Customer PII is excluded."""
    orders = store.load_orders()
    results = []
    for o in orders:
        if site and o.get("site") != site:
            continue
        if status and o.get("status") != status:
            continue
        clean = {k: v for k, v in o.items() if k not in ("customer_name", "customer_phone")}
        results.append(clean)

    results.sort(key=lambda x: (int(x.get("priority") or 3), x.get("created") or ""))
    return results


@mcp.tool()
def assign_order(id: int, crew: str) -> bool:
    """Assign a work order to a crew."""
    return assign.assign_order(id, crew)


@mcp.tool()
def close_order(id: int) -> bool:
    """Close a work order."""
    res = store.update_order(id, status="closed")
    return res is not None


if __name__ == "__main__":
    mcp.run(transport="stdio")
