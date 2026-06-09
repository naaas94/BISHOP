"""M0 HTTP stub for query-api."""

import logging
from http.server import BaseHTTPRequestHandler, HTTPServer

from bishop_shared.constants import STATE_WORKER_INTERNAL_PORT

SERVICE_NAME = "query-api"

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


class RootHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


def run_server() -> None:
    server = HTTPServer(("0.0.0.0", STATE_WORKER_INTERNAL_PORT), RootHandler)
    server.serve_forever()


def main() -> None:
    logger.info("service=%s status=stub_started", SERVICE_NAME)
    run_server()


if __name__ == "__main__":
    main()
