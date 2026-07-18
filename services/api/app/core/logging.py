import logging
import sys


def configure_logging() -> None:
    """Configure a single structured stdout logger for the whole app.

    Render (and most PaaS hosts) captures stdout directly, so writing
    plain structured lines there is sufficient without a log shipper.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
        force=True,
    )
