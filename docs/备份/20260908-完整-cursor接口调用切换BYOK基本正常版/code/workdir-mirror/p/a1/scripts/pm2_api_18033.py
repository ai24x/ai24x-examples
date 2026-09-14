from __future__ import annotations

import os
import sys

import uvicorn


def main() -> None:
    api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api", "server"))
    # ensure relative paths (like ./data/*.db) behave same as manual cd into api/server
    os.chdir(api_dir)
    sys.path.insert(0, api_dir)
    uvicorn.run("app.main:app", host="127.0.0.1", port=18011, reload=False)


if __name__ == "__main__":
    main()

