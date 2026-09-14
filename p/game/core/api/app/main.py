from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import Base, engine
from .routers import auth, challenges, events, leaderboard, me

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Game Core 中台", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth.router, me.router, events.router, leaderboard.router, challenges.router):
    app.include_router(r)


_PROTO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "p0-1", "prototype"))
if os.path.isdir(_PROTO_DIR):
    app.mount("/playtest", StaticFiles(directory=_PROTO_DIR, html=True), name="playtest")

_PROTOTYPES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "prototypes"))
if os.path.isdir(_PROTOTYPES_DIR):
    app.mount("/prototypes", StaticFiles(directory=_PROTOTYPES_DIR, html=True), name="prototypes")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "app": settings.app_name, "version": "0.1.0"}
