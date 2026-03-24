"""Company software catalog tool: list vendor software used at Digital Science."""

import json
import logging

from backend.tools.registry import ToolContext

logger = logging.getLogger(__name__)

COMPANY_SOFTWARE_KEY = "config/company-software.json"

LIST_COMPANY_SOFTWARE_SCHEMA = {
    "name": "list_company_software",
    "description": (
        "List all vendor software and tools used at Digital Science, with the departments "
        "that use each one. Use this to understand what tools are available across the company - "
        "for example, when brainstorming integrations, exploring automation opportunities, "
        "or suggesting tools the user might not know about."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "department": {
                "type": "string",
                "description": (
                    "Optional: filter to a specific department (e.g. 'Sales', 'Technology', "
                    "'Marketing'). Omit to see all software across the company."
                ),
            },
        },
        "required": [],
    },
}


async def list_company_software(
    context: ToolContext,
    department: str | None = None,
) -> str:
    storage = context.storage
    if storage is None:
        return "Software catalog not available."

    data = await storage.read(COMPANY_SOFTWARE_KEY)
    if data is None:
        return "No company software catalog found."

    try:
        catalog = json.loads(data.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return "Software catalog is unreadable."

    if department:
        dept_lower = department.lower()
        catalog = [
            item for item in catalog
            if any(
                dept_lower in d.lower() or d.lower() == "general"
                for d in item.get("departments", [])
            )
        ]

    if not catalog:
        return f"No software found for department '{department}'."

    lines = [f"{len(catalog)} tools:"]
    for item in catalog:
        depts = ", ".join(item.get("departments", []))
        lines.append(f"- {item['product']} ({depts})")

    return "\n".join(lines)


def register_software_tools(registry) -> None:
    registry.register(LIST_COMPANY_SOFTWARE_SCHEMA, list_company_software)
