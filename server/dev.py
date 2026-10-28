"""Run the API for local testing: `python -m server.dev [--live]`.

--live sets MONSTER_MODE=live (real SAM 3.1, Muse Spark and Muse Image calls, all cached)
before the app loads; without it the API runs in fixture mode. The API only listens on
localhost: a phone reaches it through the Vite dev server (`npm run dev:lan`), which
proxies /api.
"""

import argparse
import os

import uvicorn

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="call the real models (spends credits)")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    os.environ["MONSTER_MODE"] = "live" if args.live else os.environ.get("MONSTER_MODE", "fixture")
    print(f"Monster in the Closet API · {os.environ['MONSTER_MODE']} mode · http://127.0.0.1:{args.port}/docs")
    uvicorn.run("server.main:app", host="127.0.0.1", port=args.port)
