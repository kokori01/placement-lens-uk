"""FastAPI application serving PlacementLens analytics and dashboard."""

import sqlite3
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

from placement_lens.analytics import (
    get_ranked_jobs,
    get_skill_demand,
    get_skill_gaps,
    get_summary,
)


DASHBOARD_PATH = Path(__file__).with_name("static") / "dashboard.html"


def create_app(database_path: Path) -> FastAPI:
    """Create an API bound to one read-only analytics database."""
    resolved_database = database_path.resolve()
    app = FastAPI(
        title="PlacementLens UK API",
        description="Explainable UK data-career matching and market analytics.",
        version="0.1.0",
    )

    def connect() -> sqlite3.Connection:
        return sqlite3.connect(f"file:{resolved_database}?mode=ro", uri=True)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def dashboard() -> str:
        return DASHBOARD_PATH.read_text(encoding="utf-8")

    @app.get("/api/health")
    def health() -> dict:
        with connect() as connection:
            job_count = connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        return {"status": "ok", "jobs": int(job_count)}

    @app.get("/api/summary")
    def summary() -> dict:
        with connect() as connection:
            return get_summary(connection)

    @app.get("/api/skills")
    def skills(limit: int = Query(default=15, ge=1, le=50)) -> list:
        with connect() as connection:
            return get_skill_demand(connection, limit=limit)

    @app.get("/api/gaps")
    def gaps(limit: int = Query(default=15, ge=1, le=50)) -> list:
        with connect() as connection:
            return get_skill_gaps(connection, limit=limit)

    @app.get("/api/jobs")
    def jobs(
        source: str = "",
        level: str = "",
        limit: int = Query(default=25, ge=1, le=200),
    ) -> dict:
        with connect() as connection:
            records = get_ranked_jobs(
                connection,
                source=source,
                level=level,
                limit=limit,
            )
        return {"count": len(records), "jobs": records}

    return app
