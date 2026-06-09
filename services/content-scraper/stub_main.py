"""M0 long-running stub for content-scraper."""

import logging
import time

SERVICE_NAME = "content-scraper"

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("service=%s status=stub_started", SERVICE_NAME)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
