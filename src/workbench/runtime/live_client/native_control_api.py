"""Same-origin API for the native plugin control channel (status, arm/disarm, stop, warp, speed)."""
from __future__ import annotations

from typing import Callable, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .native_control import NativeControlError, read_status, send_command


class WarpTarget(BaseModel):
    x: float
    y: float  # height, as !logpos prints it (server Y is inverted: +Y is down)
    z: float
    id: str | None = Field(default=None, max_length=32)


class ArmRequest(BaseModel):
    mode: Literal["warp", "autorun", "local"] = "warp"
    consent: str


class ChatRequest(BaseModel):
    text: str = Field(min_length=2, max_length=120)


class SpeedRequest(BaseModel):
    value: float


def create_native_control_router(ashita_root_provider: Callable[[], str | None]) -> APIRouter:
    router = APIRouter(prefix="/live-client/native", tags=["Live Client Native"])

    def same_origin(request: Request) -> None:
        if request.client is None or request.client.host not in ("127.0.0.1", "::1", "testclient"):
            raise HTTPException(status_code=403, detail="native control requires local browser")
        origin = request.headers.get("origin")
        if not origin or origin != str(request.base_url).rstrip("/"):
            raise HTTPException(status_code=403, detail="same-origin request required")

    def root() -> str:
        value = ashita_root_provider()
        if not value:
            raise HTTPException(status_code=409, detail="no Ashita install remembered; run Bridge setup first")
        return value

    def run(cmd: str, fields: dict | None = None) -> dict:
        try:
            return send_command(root(), cmd, fields)
        except NativeControlError as exc:
            raise HTTPException(status_code=409 if exc.code in ("plugin_offline", "channel_disabled", "chat_disabled")
                                else 422, detail={"code": exc.code, "message": str(exc)}) from exc

    @router.get("/status")
    def status(request: Request) -> dict:
        if request.client is None or request.client.host not in ("127.0.0.1", "::1", "testclient"):
            raise HTTPException(status_code=403, detail="native control requires local browser")
        value = ashita_root_provider()
        if not value:
            return {"online": False, "reason": "no_ashita_root"}
        return read_status(value)

    @router.post("/arm")
    def arm(request: Request, body: ArmRequest) -> dict:
        same_origin(request)
        return run("enable", {"mode": body.mode, "consent": body.consent})

    @router.post("/disarm")
    def disarm(request: Request) -> dict:
        same_origin(request)
        return run("disable")

    @router.post("/stop")
    def stop(request: Request) -> dict:
        same_origin(request)
        return run("stop")

    @router.post("/warp")
    def warp(request: Request, target: WarpTarget) -> dict:
        same_origin(request)
        return run("warp_to", target.model_dump())

    @router.post("/chat")
    def chat(request: Request, body: ChatRequest) -> dict:
        same_origin(request)
        return run("chat", {"text": body.text})

    @router.post("/speed")
    def speed(request: Request, body: SpeedRequest) -> dict:
        same_origin(request)
        return run("speed", {"value": body.value})

    @router.post("/speed/off")
    def speed_off(request: Request) -> dict:
        same_origin(request)
        return run("speed_off")

    return router
