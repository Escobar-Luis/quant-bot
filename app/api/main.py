"""Day Trader AI API, story backend-1: serve the verdicts in one snapshot folder. Read-only, no auth, no network.

  cd app && uv run uvicorn api.main:app --reload            # serves the repo's results/
  SNAPSHOT_DIR=/path/to/snapshot uv run uvicorn api.main:app  # a folder holding results/<course>/<version>.json

Every number comes from the results files as written (rule 3: the code decides, the API only repeats it). Every
response carries the snapshot id: in the body of our own shapes and in the X-Snapshot-Id header.
"""
import json
import logging
import os
import time
import traceback
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import snapshot as snap

REPO = Path(__file__).resolve().parent.parent.parent
log = logging.getLogger("api")
if not log.handlers:   # one JSON line per request on stderr, next to uvicorn's own lines
    log.addHandler(logging.StreamHandler())
    log.setLevel(logging.INFO)
    log.propagate = False


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def create_app(snapshot_dir: Path | str | None = None) -> FastAPI:
    root = Path(snapshot_dir or os.getenv("SNAPSHOT_DIR") or REPO)
    s = snap.load(root)
    for sk in s.skipped:
        log.warning(json.dumps({"skipped": sk["path"], "why": sk["why"], "snapshot_id": s.snapshot_id}))
    app = FastAPI(title="Day Trader AI API", version="0.1.0")
    app.state.snapshot = s

    def line(request: Request, status: int, t0: float) -> dict:
        return {"method": request.method, "path": request.url.path, "status": status,
                "ms": round((time.perf_counter() - t0) * 1000, 1), "snapshot_id": s.snapshot_id}

    @app.middleware("http")
    async def stamp_and_log(request: Request, call_next):
        request.state.t0 = t0 = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Snapshot-Id"] = s.snapshot_id
        log.info(json.dumps(line(request, response.status_code, t0)))
        return response

    def envelope(status: int, code: str, message: str) -> JSONResponse:
        return JSONResponse({"error": {"code": code, "message": message}}, status_code=status,
                            headers={"X-Snapshot-Id": s.snapshot_id})

    @app.exception_handler(ApiError)
    async def api_error(_req, e: ApiError):
        return envelope(e.status, e.code, e.message)

    @app.exception_handler(RequestValidationError)
    async def bad_request(_req, e: RequestValidationError):
        first = e.errors()[0] if e.errors() else {}
        where = ".".join(str(x) for x in first.get("loc", ()))
        return envelope(422, "bad_request", f"{where}: {first.get('msg', 'invalid request')}")

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_req, e: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(e.status_code, "http_error")
        return envelope(e.status_code, code, str(e.detail))

    @app.exception_handler(Exception)
    async def internal_error(request: Request, e: Exception):
        # Runs outside the middleware above, so it stamps and logs itself; the traceback rides inside the one line.
        t0 = getattr(request.state, "t0", time.perf_counter())
        log.error(json.dumps({**line(request, 500, t0), "error": type(e).__name__,
                              "trace": "".join(traceback.format_exception(e))}))
        return envelope(500, "internal_error", "Something broke on our side.")

    def course_or_404(course: str) -> None:
        if course not in s.files:
            raise ApiError(404, "unknown_course", f"No course {course!r}. Courses: {', '.join(s.courses())}.")

    def headline_view(f: snap.ResultsFile, delay: int) -> dict:
        d = f.doc
        port = f.headline_portfolio()
        return {"course": f.course, "course_name": d.get("course_name"), "version": f.version,
                "sample": d.get("sample", False), "partial": d.get("partial", False),
                "delay_min": delay, "delays_min": d["delays_min"], "default_delay_min": d["default_delay_min"],
                "money_start": d.get("money_start"), "window": d.get("window"), "hold": d.get("hold"),
                "portfolio": {"id": port["id"], "label": port.get("label")},
                "headline": port["by_delay"][str(delay)],
                "generated_at": d.get("generated_at"), "git_sha": d.get("git_sha")}

    @app.api_route("/health", methods=["GET", "HEAD"])
    def health():
        """ok is false when no course can be served (an empty or fully skipped snapshot)."""
        return {"ok": bool(s.files), "snapshot_id": s.snapshot_id, "courses": s.courses(), "skipped": s.skipped}

    @app.get("/v1/courses")
    def courses():
        out = []
        for c in s.courses():
            f = s.headline(c)
            out.append({**headline_view(f, f.doc["default_delay_min"]), "versions": s.versions(c)})
        return {"snapshot_id": s.snapshot_id, "courses": out}

    @app.get("/v1/courses/{course}/verdict")
    def verdict(course: str, delay: int | None = None):
        course_or_404(course)
        f = s.headline(course)
        d = f.doc["default_delay_min"] if delay is None else delay
        if d not in f.doc["delays_min"]:
            raise ApiError(422, "delay_not_precomputed",
                           f"{d} min isn't in this file. Precomputed delays: {f.doc['delays_min']}.")
        return {"snapshot_id": s.snapshot_id, **headline_view(f, d), "unknown": f.doc.get("unknown", [])}

    @app.get("/v1/courses/{course}/results/{version}")
    def results(course: str, version: str):
        course_or_404(course)
        f = s.files[course].get(version)
        if not f:
            raise ApiError(404, "unknown_version",
                           f"No {version!r} for {course}. Versions: {', '.join(s.versions(course))}.")
        return Response(f.raw, media_type="application/json")

    return app


app = create_app()
