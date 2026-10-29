"""Run the API for local testing: `python -m server.dev [--live] [--devices] [--var DIR]`.

--live sets MONSTER_MODE=live (real SAM 3.1, Muse Spark and Muse Image calls, all cached)
before the app loads; without it the API runs in fixture mode. --devices gives every browser
its own closet (MONSTER_CLOSETS=device): use it whenever someone else will open the app.
--var picks the data folder, e.g. `--var var/testers` to keep testers apart from your own closet. The API only listens on
localhost: a phone reaches it through the Vite dev server (`npm run dev:lan`), which
proxies /api.
"""

import argparse
import os

import uvicorn

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="call the real models (spends credits)")
    ap.add_argument("--devices", action="store_true", help="one closet per browser, for testers")
    ap.add_argument("--var", help="data folder (default var/)")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    os.environ["MONSTER_MODE"] = "live" if args.live else os.environ.get("MONSTER_MODE", "fixture")
    if args.devices:
        os.environ["MONSTER_CLOSETS"] = "device"
    if args.var:
        os.environ["MONSTER_VAR_DIR"] = args.var
    closets = os.environ.get("MONSTER_CLOSETS", "single")
    print(f"Monster in the Closet API · {os.environ['MONSTER_MODE']} mode · {closets} closets · http://127.0.0.1:{args.port}/docs")
    uvicorn.run("server.main:app", host="127.0.0.1", port=args.port)
