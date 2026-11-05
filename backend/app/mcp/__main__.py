import logging
import sys

from app.mcp.server import build_server


def main() -> None:
    # stdout is the protocol wire, so everything we log goes to stderr
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
