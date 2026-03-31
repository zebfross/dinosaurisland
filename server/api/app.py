"""FastAPI application factory."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from server.api.deps import set_game_manager
from server.api.game_manager import GameManager
from server.api.routes import auth, game, lobby
from server.api import ws

# Built frontend location (relative to project root)
CLIENT_DIST = Path(__file__).parent.parent.parent / "client" / "dist"


def create_app(testing: bool = False) -> FastAPI:
    manager = GameManager()
    set_game_manager(manager)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.manager = manager
        yield

    app = FastAPI(
        title="Dinosaur Island",
        description="Turn-based multiplayer dinosaur survival game",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — permissive for dev. No credentials needed (we use Bearer tokens).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API + WebSocket routes
    app.include_router(auth.router)
    app.include_router(lobby.router)
    app.include_router(game.router)
    app.include_router(ws.router)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    # Serve built frontend (if it exists)
    if not testing and CLIENT_DIST.is_dir():
        # Static assets (JS, CSS, images)
        app.mount("/assets", StaticFiles(directory=CLIENT_DIST / "assets"), name="assets")

        # SPA fallback — serve index.html for all non-API routes
        @app.get("/{path:path}")
        async def spa_fallback(path: str):
            # Try to serve the exact file first (favicon, etc.)
            file_path = CLIENT_DIST / path
            if path and file_path.is_file():
                return FileResponse(file_path)
            # Otherwise serve index.html (React Router handles client-side routing)
            return FileResponse(CLIENT_DIST / "index.html")

    return app


# For running with `uvicorn server.api.app:app`
app = create_app()
