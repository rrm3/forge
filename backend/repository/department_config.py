"""Department config repository - reads/writes department config JSON via StorageBackend."""

import json
import logging

from backend.storage import StorageBackend

logger = logging.getLogger(__name__)

CONFIG_PREFIX = "config/departments/"
ADMIN_ACCESS_KEY = "config/admin-access.json"
COMPANY_CONFIG_KEY = "config/company.json"


class DepartmentConfigRepository:
    """Reads and writes department configuration files using StorageBackend.

    Config files live at ``config/departments/{department}.json``.
    Admin access mapping lives at ``config/admin-access.json``.
    """

    def __init__(self, storage: StorageBackend):
        self.storage = storage

    async def get_department_config(self, department: str) -> dict | None:
        """Read a department's config (prompt + objectives).

        Returns None if the department config does not exist.
        """
        key = f"{CONFIG_PREFIX}{department}.json"
        data = await self.storage.read(key)
        if data is None:
            return None
        return json.loads(data.decode())

    async def save_department_config(self, department: str, config: dict) -> None:
        """Write a department's config."""
        key = f"{CONFIG_PREFIX}{department}.json"
        data = json.dumps(config, indent=2).encode()
        await self.storage.write(key, data, content_type="application/json")

    async def get_admin_access(self) -> dict:
        """Read the admin access mapping (email -> list of departments).

        Returns an empty dict if the file does not exist.
        """
        data = await self.storage.read(ADMIN_ACCESS_KEY)
        if data is None:
            return {}
        return json.loads(data.decode())

    async def save_admin_access(self, access: dict) -> None:
        """Write the admin access mapping."""
        data = json.dumps(access, indent=2).encode()
        await self.storage.write(ADMIN_ACCESS_KEY, data, content_type="application/json")

    async def get_company_config(self) -> dict | None:
        """Read the company-wide config (prompt shared across all sessions).

        Returns None if the company config does not exist.
        """
        data = await self.storage.read(COMPANY_CONFIG_KEY)
        if data is None:
            return None
        return json.loads(data.decode())

    async def save_company_config(self, config: dict) -> None:
        """Write the company-wide config."""
        data = json.dumps(config, indent=2).encode()
        await self.storage.write(COMPANY_CONFIG_KEY, data, content_type="application/json")

    async def list_departments(self) -> list[str]:
        """List all departments that have config files.

        Returns department slugs (filenames without the .json extension).
        """
        keys = await self.storage.list_keys(CONFIG_PREFIX)
        departments: list[str] = []
        for key in keys:
            if key.endswith(".json"):
                # Strip prefix and .json suffix to get the department slug
                slug = key[len(CONFIG_PREFIX):-len(".json")]
                if slug:
                    departments.append(slug)
        return sorted(departments)
