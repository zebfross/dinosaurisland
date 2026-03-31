"""Shared fixtures for API tests."""

import pytest
import httpx
from httpx import ASGITransport

from server.api.app import create_app
from server.api.deps import get_manager


@pytest.fixture
def app():
    return create_app(testing=True)


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def auth_client(client):
    """Client with a registered player and auth headers."""
    r = await client.post("/api/auth/register", json={"username": "testplayer"})
    token = r.json()["token"]
    player_id = r.json()["player_id"]
    client.headers["Authorization"] = f"Bearer {token}"
    client._player_id = player_id
    client._token = token
    yield client


@pytest.fixture
async def game_with_player(auth_client):
    """A game created and joined by the auth player, not yet started."""
    r = await auth_client.post("/api/games", json={"width": 15, "height": 15})
    game_id = r.json()["game_id"]

    r = await auth_client.post(
        f"/api/games/{game_id}/join",
        json={"species_name": "TestDinos", "diet": "herbivore"},
    )
    species_id = r.json()["species_id"]

    return game_id, species_id
