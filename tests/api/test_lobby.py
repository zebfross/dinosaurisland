"""Tests for lobby API endpoints."""

import pytest


class TestAuth:
    async def test_register(self, client):
        r = await client.post("/api/auth/register", json={"username": "alice"})
        assert r.status_code == 200
        data = r.json()
        assert "token" in data
        assert "player_id" in data

    async def test_register_same_user_new_token(self, client):
        r1 = await client.post("/api/auth/register", json={"username": "bob"})
        token1 = r1.json()["token"]
        r2 = await client.post("/api/auth/register", json={"username": "bob"})
        token2 = r2.json()["token"]
        assert token1 != token2
        assert r1.json()["player_id"] == r2.json()["player_id"]

    async def test_register_empty_username(self, client):
        r = await client.post("/api/auth/register", json={"username": ""})
        assert r.status_code == 400


class TestCreateGame:
    async def test_create_game(self, auth_client):
        r = await auth_client.post("/api/games", json={"width": 20, "height": 20})
        assert r.status_code == 200
        data = r.json()
        assert data["phase"] == "waiting"
        assert data["player_count"] == 0

    async def test_create_game_no_auth(self, client):
        r = await client.post("/api/games", json={})
        assert r.status_code == 422  # missing auth header

    async def test_list_games(self, auth_client):
        await auth_client.post("/api/games", json={})
        await auth_client.post("/api/games", json={})
        r = await auth_client.get("/api/games")
        assert r.status_code == 200
        assert len(r.json()) >= 2


class TestJoinGame:
    async def test_join_game(self, auth_client, game_with_player):
        game_id, species_id = game_with_player
        assert species_id is not None

        # Verify game now has 1 player
        r = await auth_client.get(f"/api/games/{game_id}")
        assert r.json()["player_count"] == 1

    async def test_join_nonexistent_game(self, auth_client):
        r = await auth_client.post(
            "/api/games/fake-id/join",
            json={"species_name": "X", "diet": "herbivore"},
        )
        assert r.status_code == 400

    async def test_double_join(self, auth_client, game_with_player):
        game_id, _ = game_with_player
        r = await auth_client.post(
            f"/api/games/{game_id}/join",
            json={"species_name": "X", "diet": "carnivore"},
        )
        assert r.status_code == 400  # already joined


class TestStartGame:
    async def test_start_game(self, auth_client, game_with_player):
        game_id, _ = game_with_player
        r = await auth_client.post(f"/api/games/{game_id}/start")
        assert r.status_code == 200
        assert r.json()["status"] == "started"

    async def test_start_empty_game(self, auth_client):
        r = await auth_client.post("/api/games", json={})
        game_id = r.json()["game_id"]
        r = await auth_client.post(f"/api/games/{game_id}/start")
        assert r.status_code == 400
