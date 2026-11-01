"""Run the API for local testing: `python -m server.dev [--live] [--devices] [--var DIR]`.

--live sets MONSTER_MODE=live (real SAM 3.1, Muse Spark and Muse Image calls, all cached)
before the app loads; without it the API runs in fixture mode. --devices gives every browser
its own closet (MONSTER_CLOSETS=device): use it whenever someone else will open the app.
--var picks the data folder, e.g. `--var var/testers` to keep testers apart from your own closet. The API only listens on
localhost: a phone reaches it through the Vite dev server (`npm run dev:lan`), which
proxies /api.

--public is for a link testers open from anywhere (through a tunnel, see README "Testing on your
phone"): one closet per browser, the daily spend caps on, and the built app (`npm run build`)
served by the API itself, so one port is all the tunnel needs.
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
    ap.add_argument("--public", action="store_true", help="for a tunnel: per-device closets, spend caps, serve the built app")
    args = ap.parse_args()
    if args.public:
        from pathlib import Path
        if not (Path(__file__).resolve().parent.parent / "web" / "dist" / "index.html").exists():
            raise SystemExit("--public serves the built app: run `npm run build` in web/ first.")
        args.devices = True
        os.environ.setdefault("MONSTER_DAILY_CALLS", "300")
        os.environ.setdefault("MONSTER_CLOSET_DAILY_CALLS", "25")
        os.environ.setdefault("MONSTER_MAX_CLOSETS", "200")
    os.environ["MONSTER_MODE"] = "live" if args.live else os.environ.get("MONSTER_MODE", "fixture")
    if args.devices:
        os.environ["MONSTER_CLOSETS"] = "device"
    if args.var:
        os.environ["MONSTER_VAR_DIR"] = args.var
    closets = os.environ.get("MONSTER_CLOSETS", "single")
    caps = f" · caps {os.environ['MONSTER_DAILY_CALLS']}/day, {os.environ['MONSTER_CLOSET_DAILY_CALLS']}/closet" if args.public else ""
    print(f"Monster in the Closet API · {os.environ['MONSTER_MODE']} mode · {closets} closets{caps} · http://127.0.0.1:{args.port}/")
    uvicorn.run("server.main:app", host="127.0.0.1", port=args.port)
