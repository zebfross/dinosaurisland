"""Tests for game API endpoints."""

import pytest


async def _start_game(auth_client, game_with_player):
    """Helper to start a game and return game_id, species_id."""
    game_id, species_id = game_with_player
    await auth_client.post(f"/api/games/{game_id}/start")
    return game_id, species_id


class TestGameState:
    async def test_get_state(self, auth_client, game_with_player):
        game_id, species_id = await _start_game(auth_client, game_with_player)
        r = await auth_client.get(f"/api/games/{game_id}/state")
        assert r.status_code == 200
        data = r.json()
        assert data["turn"] == 0
        assert data["phase"] == "active"
        assert len(data["visible_cells"]) > 0
        assert len(data["dinosaurs"]) == 1
        assert data["dinosaurs"][0]["is_mine"] is True

    async def test_state_not_member(self, client, auth_client, game_with_player):
        game_id, _ = game_with_player
        # Register a different player
        r = await client.post("/api/auth/register", json={"username": "stranger"})
        token2 = r.json()["token"]
        r = await client.get(
            f"/api/games/{game_id}/state",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert r.status_code == 404


class TestActions:
    async def test_submit_rest(self, auth_client, game_with_player):
        game_id, _ = await _start_game(auth_client, game_with_player)

        # Get dino id
        r = await auth_client.get(f"/api/games/{game_id}/state")
        dino_id = r.json()["dinosaurs"][0]["id"]

        r = await auth_client.post(
            f"/api/games/{game_id}/actions",
            json={"actions": [{"dino_id": dino_id, "action_type": "rest"}]},
        )
        assert r.status_code == 200
        assert r.json()["accepted"] == 1
        assert r.json()["errors"] == []

    async def test_submit_move(self, auth_client, game_with_player):
        game_id, _ = await _start_game(auth_client, game_with_player)

        # Get dino and legal moves
        r = await auth_client.get(f"/api/games/{game_id}/state")
        dino_id = r.json()["dinosaurs"][0]["id"]

        r = await auth_client.get(f"/api/games/{game_id}/legal-actions/{dino_id}")
        actions = r.json()["actions"]
        moves = [a for a in actions if a["action_type"] == "move"]
        assert len(moves) > 0

        # Submit a move
        move = moves[0]
        r = await auth_client.post(
            f"/api/games/{game_id}/actions",
            json={"actions": [move]},
        )
        assert r.status_code == 200
        assert r.json()["accepted"] == 1

    async def test_submit_invalid_action(self, auth_client, game_with_player):
        game_id, _ = await _start_game(auth_client, game_with_player)

        r = await auth_client.post(
            f"/api/games/{game_id}/actions",
            json={"actions": [{"dino_id": "fake", "action_type": "rest"}]},
        )
        assert r.status_code == 200
        assert r.json()["accepted"] == 0
        assert len(r.json()["errors"]) == 1


class TestLegalActions:
    async def test_get_legal_actions(self, auth_client, game_with_player):
        game_id, _ = await _start_game(auth_client, game_with_player)

        r = await auth_client.get(f"/api/games/{game_id}/state")
        dino_id = r.json()["dinosaurs"][0]["id"]

        r = await auth_client.get(f"/api/games/{game_id}/legal-actions/{dino_id}")
        assert r.status_code == 200
        actions = r.json()["actions"]
        # Should at least have rest
        types = [a["action_type"] for a in actions]
        assert "rest" in types


class TestScores:
    async def test_get_scores(self, auth_client, game_with_player):
        game_id, _ = await _start_game(auth_client, game_with_player)
        r = await auth_client.get(f"/api/games/{game_id}/scores")
        assert r.status_code == 200
        scores = r.json()
        assert len(scores) == 1
        assert scores[0]["name"] == "TestDinos"
