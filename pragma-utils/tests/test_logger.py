import pytest
import logging

from pragma_utils.logger import setup_logging


def test_setup_logging():
    # Create a test logger
    test_logger = logging.getLogger("test_logger")

    # Test valid log level
    setup_logging(test_logger, "INFO")
    assert test_logger.level == logging.INFO
    assert logging.getLogger().level == logging.INFO

    # Test another valid log level
    setup_logging(test_logger, "DEBUG")
    assert test_logger.level == logging.DEBUG
    assert logging.getLogger().level == logging.DEBUG

    # Test case-insensitivity
    setup_logging(test_logger, "warning")
    assert test_logger.level == logging.WARNING
    assert logging.getLogger().level == logging.WARNING

    # Test invalid log level
    with pytest.raises(ValueError) as excinfo:
        setup_logging(test_logger, "INVALID_LEVEL")
    assert "Invalid log level: INVALID_LEVEL" in str(excinfo.value)
