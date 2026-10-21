"""Open the generated map locally in your default browser."""

import argparse
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).parent
MAP_FILES = ("nyc_tree_map.html", "canopy_by_borough.html")


def main() -> None:
    parser = argparse.ArgumentParser(description="Open a generated NYC map in your browser.")
    parser.add_argument(
        "map_file",
        nargs="?",
        choices=MAP_FILES,
        default="nyc_tree_map.html",
        help="Map to open (default: nyc_tree_map.html).",
    )
    args = parser.parse_args()
    map_file = ROOT / args.map_file

    if not map_file.is_file():
        generator = (
            "canopy_by_borough.py"
            if args.map_file == "canopy_by_borough.html"
            else "economic_census_data_in_nyc.py"
        )
        raise SystemExit(f"Map not found. Run {generator} first.")

    handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT))
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        url = f"http://127.0.0.1:{server.server_port}/{args.map_file}"
        print(f"Opening {url}")
        print("Keep this window open while viewing the map. Press Ctrl+C to stop.")
        webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nMap server stopped.")


if __name__ == "__main__":
    main()
