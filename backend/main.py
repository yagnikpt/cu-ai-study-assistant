"""Entry point for the AI Study Assistant API server.

Run from the backend/ directory:
    uv run python main.py
"""

import uvicorn


def main():
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
