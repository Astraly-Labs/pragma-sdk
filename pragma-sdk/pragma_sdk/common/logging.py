import logging
from logging import Logger
from sys import stdout

logger = logging.getLogger(__name__)


def get_pragma_sdk_logger() -> Logger:
    """
    Return the logger with a stream handler.
    Log format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    The logger level is set to DEBUG.
    There can only be one stream handler.
    """

    global logger

    logger.setLevel(logging.DEBUG)
    stream_handler = logging.StreamHandler(stdout)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    stream_handler.setFormatter(formatter)
    if logger.hasHandlers():
        logger.handlers.clear()
    logger.addHandler(stream_handler)

    return logger
