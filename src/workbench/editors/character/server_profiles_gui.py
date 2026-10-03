"""Named server/environment profile API mounted below the Character Editor router.

The Character Editor router is already registered on the live FastAPI app, so keeping the profile
API here avoids adding another hook to the monolithic ``gui_server.py`` while still making the
selected profile global through ``workbench.runtime.legacy_settings``.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from workbench.runtime import server_profiles
from workbench.runtime.legacy_settings import ensure_server_profiles_seeded

from .factory import open_character_editor

router = APIRouter(prefix="/environments", tags=["Server Environments"])


def _store():
    ensure_server_profiles_seeded()
    return server_profiles.connect()


def _payload(profile):
    return profile.public_dict() if profile is not None else None


@router.get("/profiles.json")
def server_environment_profiles():
    con = _store()
    try:
        rows = server_profiles.list_profiles(con)
        active = server_profiles.get_active_profile(con)
        return JSONResponse(
            {
                "profiles": [_payload(row) for row in rows],
                "active": _payload(active),
                "families": ["auto", "lsb", "topaz", "dsp"],
                "environments": ["live", "test", "dev", "backup", "other"],
            }
        )
    finally:
        con.close()


@router.post("/profiles")
async def create_server_environment(request: Request):
    body = await request.json()
    con = _store()
    try:
        try:
            profile = server_profiles.create_profile(
                con,
                name=str(body.get("name") or ""),
                server_root=str(body.get("server_root") or ""),
                family=str(body.get("family") or "auto"),
                environment=str(body.get("environment") or "other"),
                enabled=bool(body.get("enabled", True)),
                notes=str(body.get("notes") or ""),
                make_active=bool(body.get("make_active", False)),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return JSONResponse(_payload(profile))
    finally:
        con.close()


@router.post("/profiles/{profile_id}")
async def update_server_environment(profile_id: int, request: Request):
    body = await request.json()
    con = _store()
    try:
        current = server_profiles.get_profile(con, profile_id)
        if current is None:
            raise HTTPException(status_code=404, detail="Server profile not found")
        try:
            profile = server_profiles.update_profile(
                con,
                profile_id,
                name=str(body.get("name", current.name)),
                server_root=str(body.get("server_root", current.server_root)),
                family=str(body.get("family", current.family)),
                environment=str(body.get("environment", current.environment)),
                enabled=bool(body.get("enabled", current.enabled)),
                notes=str(body.get("notes", current.notes)),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return JSONResponse(_payload(profile))
    finally:
        con.close()


@router.post("/profiles/{profile_id}/activate")
def activate_server_environment(profile_id: int):
    con = _store()
    try:
        try:
            profile = server_profiles.set_active_profile(con, profile_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return JSONResponse({"active": _payload(profile)})
    finally:
        con.close()


@router.post("/profiles/{profile_id}/delete")
def delete_server_environment(profile_id: int):
    con = _store()
    try:
        profile = server_profiles.get_profile(con, profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Server profile not found")
        if profile.is_active:
            raise HTTPException(status_code=409, detail="Select another server environment before deleting the active profile")
        server_profiles.delete_profile(con, profile_id)
        return JSONResponse({"status": "deleted", "profile_id": profile_id})
    finally:
        con.close()


@router.post("/profiles/{profile_id}/test")
def test_server_environment(profile_id: int):
    con = _store()
    try:
        profile = server_profiles.get_profile(con, profile_id)
    finally:
        con.close()
    if profile is None:
        raise HTTPException(status_code=404, detail="Server profile not found")

    root = Path(profile.server_root).expanduser()
    if not root.is_dir():
        raise HTTPException(status_code=400, detail=f"Server root does not exist: {root}")

    try:
        context = open_character_editor(root)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    try:
        status = context.public_status()
        cursor = context.service.connection.cursor()
        try:
            cursor.execute("SELECT VERSION()")
            row = cursor.fetchone()
            version = str(row[0]) if row else "unknown"
        finally:
            cursor.close()
        return JSONResponse(
            {
                "status": "ok",
                "profile": _payload(profile),
                "database": status.get("database", {}),
                "adapter": status.get("adapter", {}),
                "server_version": version,
            }
        )
    finally:
        context.close()


# ``workbench.editors.character.__init__`` imports this module before ``gui.py``.  Attach this
# API to the already-included audit subrouter so the live app receives it without another
# gui_server.py registration hook.
from .audit_gui import router as _character_subrouter

_character_subrouter.include_router(router)
