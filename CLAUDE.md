# Dinosaur Island

Turn-based multiplayer dinosaur survival game inspired by the Facebook engineering puzzle.

## Project Structure
- `server/engine/` — Pure game logic, ZERO I/O, fully testable
- `server/api/` — FastAPI REST + WebSocket layer
- `server/bots/` — AI bot framework
- `server/cli/` — Text-mode interface
- `client/` — React + Canvas frontend
- `tests/` — pytest test suite

## Development
```bash
pip install -e ".[dev,mapgen]"
pytest
```

## Conventions
- Game engine has NO I/O imports — pure logic only
- All randomness injected via `random.Random` for deterministic testing
- Models use Pydantic v2
- Map coordinates: `cells[y][x]` (row-major), accessed via `get_cell(x, y)`
- Tests mirror source structure under `tests/`
