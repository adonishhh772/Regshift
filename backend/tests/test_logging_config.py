from app.logging_config import configure_logging, resolve_log_level
import logging


def test_configure_logging_sets_root_handler():
    configure_logging()
    root_logger = logging.getLogger()
    assert root_logger.handlers
    assert root_logger.level == resolve_log_level()
