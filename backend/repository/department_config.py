"""Department config repository - reads/writes department config JSON via StorageBackend."""

import json
import logging

from backend.storage import StorageBackend

logger = logging.getLogger(__name__)

CONFIG_PREFIX = "config/departments/"
DEPT_PROMPT_PREFIX = "config/departments/prompt/"
DEPT_OBJECTIVES_PREFIX = "config/departments/objectives/"
ADMIN_ACCESS_KEY = "config/admin-access.json"
COMPANY_CONFIG_KEY = "config/company.json"
COMPANY_PROMPT_KEY = "config/company-prompt.json"
COMPANY_OBJECTIVES_KEY = "config/company-objectives.json"


class DepartmentConfigRepository:
    """Reads and writes department configuration files using StorageBackend.

    Config files live at ``config/departments/{department}.json``.
    Admin access mapping lives at ``config/admin-access.json``.
    """

    def __init__(self, storage: StorageBackend):
        self.storage = storage

    async def get_department_config(self, department: str) -> dict | None:
        """Read a department's config (prompt + objectives merged).

        Reads prompt and objectives from separate files. Falls back to the
        legacy combined ``departments/{department}.json`` if the split files
        don't exist yet.
        """
        prompt_key = f"{DEPT_PROMPT_PREFIX}{department}.json"
        objectives_key = f"{DEPT_OBJECTIVES_PREFIX}{department}.json"

        prompt_data = await self.storage.read(prompt_key)
        objectives_data = await self.storage.read(objectives_key)

        if prompt_data is None and objectives_data is None:
            # Fallback: read legacy combined file
            legacy_key = f"{CONFIG_PREFIX}{department}.json"
            data = await self.storage.read(legacy_key)
            if data is None:
                return None
            return json.loads(data.decode())

        # If only one split file exists, backfill the missing half from the
        # legacy file so a partial migration doesn't silently drop data.
        if prompt_data is None or objectives_data is None:
            legacy_key = f"{CONFIG_PREFIX}{department}.json"
            legacy_raw = await self.storage.read(legacy_key)
            legacy = json.loads(legacy_raw.decode()) if legacy_raw else {}
        else:
            legacy = {}

        prompt = json.loads(prompt_data.decode()).get("prompt", "") if prompt_data else legacy.get("prompt", "")
        objectives = json.loads(objectives_data.decode()).get("objectives", []) if objectives_data else legacy.get("objectives", [])
        return {"prompt": prompt, "objectives": objectives}

    async def save_department_config(self, department: str, config: dict) -> None:
        """Write prompt and objectives to their separate files."""
        if "prompt" in config:
            await self.save_department_prompt(department, config["prompt"])
        if "objectives" in config:
            await self.save_department_objectives(department, config["objectives"])

    async def get_department_prompt(self, department: str) -> str | None:
        """Read a department's prompt only."""
        prompt_key = f"{DEPT_PROMPT_PREFIX}{department}.json"
        data = await self.storage.read(prompt_key)
        if data is not None:
            return json.loads(data.decode()).get("prompt", "")
        # Fallback to legacy combined file
        legacy_key = f"{CONFIG_PREFIX}{department}.json"
        legacy_data = await self.storage.read(legacy_key)
        if legacy_data is None:
            return None
        return json.loads(legacy_data.decode()).get("prompt", "")

    async def save_department_prompt(self, department: str, prompt: str) -> None:
        """Write a department's prompt (separate from objectives)."""
        key = f"{DEPT_PROMPT_PREFIX}{department}.json"
        data = json.dumps({"prompt": prompt}, indent=2).encode()
        await self.storage.write(key, data, content_type="application/json")

    async def get_department_objectives(self, department: str) -> list | None:
        """Read a department's objectives only."""
        objectives_key = f"{DEPT_OBJECTIVES_PREFIX}{department}.json"
        data = await self.storage.read(objectives_key)
        if data is not None:
            return json.loads(data.decode()).get("objectives", [])
        # Fallback to legacy combined file
        legacy_key = f"{CONFIG_PREFIX}{department}.json"
        legacy_data = await self.storage.read(legacy_key)
        if legacy_data is None:
            return None
        return json.loads(legacy_data.decode()).get("objectives", [])

    async def save_department_objectives(self, department: str, objectives: list) -> None:
        """Write a department's objectives (separate from prompt)."""
        key = f"{DEPT_OBJECTIVES_PREFIX}{department}.json"
        data = json.dumps({"objectives": objectives}, indent=2).encode()
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
        """Read the company-wide config (prompt + objectives merged).

        Reads prompt and objectives from separate files. Falls back to the
        legacy combined ``company.json`` if the split files don't exist yet.
        """
        prompt_data = await self.storage.read(COMPANY_PROMPT_KEY)
        objectives_data = await self.storage.read(COMPANY_OBJECTIVES_KEY)

        if prompt_data is None and objectives_data is None:
            # Fallback: read legacy combined file
            data = await self.storage.read(COMPANY_CONFIG_KEY)
            if data is None:
                return None
            return json.loads(data.decode())

        # If only one split file exists, backfill the missing half from the
        # legacy file so a partial migration doesn't silently drop data.
        if prompt_data is None or objectives_data is None:
            legacy_data = await self.storage.read(COMPANY_CONFIG_KEY)
            legacy = json.loads(legacy_data.decode()) if legacy_data else {}
        else:
            legacy = {}

        prompt = json.loads(prompt_data.decode()).get("prompt", "") if prompt_data else legacy.get("prompt", "")
        objectives = json.loads(objectives_data.decode()).get("objectives", []) if objectives_data else legacy.get("objectives", [])
        return {"prompt": prompt, "objectives": objectives}

    async def save_company_prompt(self, prompt: str) -> None:
        """Write the company-wide prompt (separate from objectives)."""
        data = json.dumps({"prompt": prompt}, indent=2).encode()
        await self.storage.write(COMPANY_PROMPT_KEY, data, content_type="application/json")

    async def save_company_objectives(self, objectives: list) -> None:
        """Write the company-wide objectives (separate from prompt)."""
        data = json.dumps({"objectives": objectives}, indent=2).encode()
        await self.storage.write(COMPANY_OBJECTIVES_KEY, data, content_type="application/json")

    async def save_company_config(self, config: dict) -> None:
        """Write prompt and objectives to their separate files."""
        if "prompt" in config:
            await self.save_company_prompt(config["prompt"])
        if "objectives" in config:
            await self.save_company_objectives(config["objectives"])

    async def get_merged_objectives(self, department: str, program_week: int | None = None) -> list[dict]:
        """Return company-wide objectives + department-specific objectives merged.

        Company objectives come first, then any department extras.
        If program_week is provided, only objectives with week_introduced <= program_week
        are included. Objectives without week_introduced are always included (default: week 1).
        Returns an empty list if neither config exists.
        """
        company_config = await self.get_company_config()
        company_objectives = (company_config or {}).get("objectives", [])

        dept_config = await self.get_department_config(department)
        dept_objectives = (dept_config or {}).get("objectives", [])

        all_objectives = company_objectives + dept_objectives

        if program_week is not None:
            all_objectives = [
                o for o in all_objectives
                if o.get("week_introduced", 1) <= program_week
            ]

        return all_objectives

    async def list_departments(self) -> list[str]:
        """List all departments that have config files.

        Returns department slugs (filenames without the .json extension).
        Checks both legacy combined files and split prompt/objectives files.
        """
        departments: set[str] = set()

        # Legacy combined files: config/departments/{slug}.json
        keys = await self.storage.list_keys(CONFIG_PREFIX)
        for key in keys:
            if key.endswith(".json"):
                slug = key[len(CONFIG_PREFIX):-len(".json")]
                # Skip split file subdirectories (prompt/*, objectives/*)
                if slug and "/" not in slug:
                    departments.add(slug)

        # Split prompt files: config/departments/prompt/{slug}.json
        prompt_keys = await self.storage.list_keys(DEPT_PROMPT_PREFIX)
        for key in prompt_keys:
            if key.endswith(".json"):
                slug = key[len(DEPT_PROMPT_PREFIX):-len(".json")]
                if slug:
                    departments.add(slug)

        # Split objectives files: config/departments/objectives/{slug}.json
        obj_keys = await self.storage.list_keys(DEPT_OBJECTIVES_PREFIX)
        for key in obj_keys:
            if key.endswith(".json"):
                slug = key[len(DEPT_OBJECTIVES_PREFIX):-len(".json")]
                if slug:
                    departments.add(slug)

        return sorted(departments)
