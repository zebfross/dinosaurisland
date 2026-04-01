"""Entry point: python -m server [cli|serve]"""

import sys


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "cli"

    if mode == "serve":
        import uvicorn
        host = "0.0.0.0"
        port = 8800
        # Check for --port flag
        for i, arg in enumerate(sys.argv):
            if arg == "--port" and i + 1 < len(sys.argv):
                port = int(sys.argv[i + 1])
            elif arg == "--host" and i + 1 < len(sys.argv):
                host = sys.argv[i + 1]
        print(f"Starting Dinosaur Island server on {host}:{port}")
        uvicorn.run("server.api.app:app", host=host, port=port, reload=False)
    elif mode == "cli":
        from server.cli.runner import run
        run()
    else:
        print(f"Usage: python -m server [cli|serve]")
        print(f"  cli   — Interactive terminal game (default)")
        print(f"  serve — Start the web API server")
        sys.exit(1)


if __name__ == "__main__":
    main()
