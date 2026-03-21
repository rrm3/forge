"""Org chart service - loads a SQLite database into memory for fast lookups.

The org chart file is stored on S3 (production) or local filesystem (dev).
It's loaded once at startup into an in-memory SQLite database. The schema
is not hardcoded - columns are accessed by name with fallback defaults.
"""

from __future__ import annotations

import logging
import sqlite3
from collections import deque
from pathlib import Path

logger = logging.getLogger(__name__)


class OrgChart:
    """In-memory org chart backed by SQLite."""

    def __init__(self, db: sqlite3.Connection):
        self._db = db
        self._db.row_factory = sqlite3.Row

    @classmethod
    def from_file(cls, path: str | Path) -> OrgChart:
        """Load a SQLite file into an in-memory database."""
        file_db = sqlite3.connect(str(path))
        mem_db = sqlite3.connect(":memory:", check_same_thread=False)
        file_db.backup(mem_db)
        file_db.close()
        return cls(mem_db)

    def count(self) -> int:
        """Total number of people in the org chart."""
        row = self._db.execute("SELECT COUNT(*) FROM people").fetchone()
        return row[0] if row else 0

    def lookup_by_email(self, email: str) -> sqlite3.Row | None:
        """Find a person by email (case-insensitive)."""
        row = self._db.execute(
            "SELECT * FROM people WHERE LOWER(email) = LOWER(?)", (email,)
        ).fetchone()
        return row

    def lookup_by_name(self, name: str) -> sqlite3.Row | None:
        """Find a person by name (case-insensitive)."""
        row = self._db.execute(
            "SELECT * FROM people WHERE LOWER(name) = LOWER(?)", (name,)
        ).fetchone()
        return row

    def find_direct_reports(self, name: str) -> list[str]:
        """Return names of all people whose reports_to matches this name."""
        rows = self._db.execute(
            "SELECT name FROM people WHERE LOWER(reports_to) = LOWER(?)", (name,)
        ).fetchall()
        return [r["name"] for r in rows]

    def get_chain_above(self, name: str) -> list[dict]:
        """Walk up the reports_to chain from a person to the top.

        Returns a list of dicts with name and title, from immediate manager
        up to the CEO (or whoever has no reports_to).
        """
        chain = []
        visited = set()
        current = name

        while current:
            if current.lower() in visited:
                break  # cycle protection
            visited.add(current.lower())

            person = self.lookup_by_name(current)
            if not person:
                break

            manager_name = person["reports_to"]
            if not manager_name:
                break

            manager = self.lookup_by_name(manager_name)
            if not manager:
                chain.append({"name": manager_name, "title": ""})
                break

            chain.append({
                "name": manager["name"],
                "title": manager["title"] or "",
            })
            current = manager_name

        return chain

    def get_tree_below(self, name: str) -> list[dict]:
        """BFS traversal of all reports under a person.

        Returns a flat list of dicts with name, title, and depth (1 = direct report).
        """
        result = []
        queue: deque[tuple[str, int]] = deque()

        for report_name in self.find_direct_reports(name):
            queue.append((report_name, 1))

        visited = {name.lower()}
        while queue:
            current_name, depth = queue.popleft()
            if current_name.lower() in visited:
                continue
            visited.add(current_name.lower())

            person = self.lookup_by_name(current_name)
            result.append({
                "name": current_name,
                "title": person["title"] if person else "",
                "depth": depth,
            })

            for sub_report in self.find_direct_reports(current_name):
                if sub_report.lower() not in visited:
                    queue.append((sub_report, depth + 1))

        return result

    def close(self):
        """Close the in-memory database."""
        try:
            self._db.close()
        except Exception:
            pass


def enrich_profile_kwargs(orgchart: OrgChart, email: str) -> dict:
    """Return a dict of profile fields populated from the org chart.

    Uses .get()-style access with defaults so it handles schema changes gracefully.
    """
    entry = orgchart.lookup_by_email(email)
    if not entry:
        return {}

    keys = entry.keys()
    result = {}

    if "title" in keys and entry["title"]:
        result["title"] = entry["title"]
    if "department" in keys and entry["department"]:
        result["department"] = entry["department"]
    if "reports_to" in keys and entry["reports_to"]:
        result["manager"] = entry["reports_to"]
    if "product" in keys and entry["product"]:
        result["team"] = entry["product"]
    if "location" in keys and entry["location"]:
        result["location"] = entry["location"]
    if "start_date" in keys and entry["start_date"]:
        result["start_date"] = entry["start_date"]
    # work_summary intentionally NOT pre-filled from org chart.
    # It should come from the user's own description during intake.

    # Find direct reports by name
    name = entry["name"] if "name" in keys else None
    if name:
        reports = orgchart.find_direct_reports(name)
        if reports:
            result["direct_reports"] = reports

    return result


def load_orgchart_from_s3(bucket: str, key: str) -> OrgChart | None:
    """Download org chart from S3 to /tmp, load into memory, clean up."""
    try:
        import boto3
        s3 = boto3.client("s3")
        local_path = Path("/tmp/org-chart.db")
        logger.info("Downloading org chart from s3://%s/%s", bucket, key)
        s3.download_file(bucket, key, str(local_path))
        oc = OrgChart.from_file(local_path)
        local_path.unlink(missing_ok=True)
        logger.info("Org chart loaded: %d people", oc.count())
        return oc
    except Exception:
        logger.warning("Failed to load org chart from S3", exc_info=True)
        return None


def load_orgchart_local(path: str) -> OrgChart | None:
    """Load org chart from a local file path."""
    p = Path(path)
    if not p.exists():
        logger.info("Org chart file not found: %s", path)
        return None
    try:
        oc = OrgChart.from_file(p)
        logger.info("Org chart loaded from %s: %d people", path, oc.count())
        return oc
    except Exception:
        logger.warning("Failed to load org chart from %s", path, exc_info=True)
        return None
