import logging
from typing import Optional, List
from pathlib import Path

from tests.integration.constants import CONTRACTS_COMPILED_DIR

logger = logging.getLogger(__name__)


def read_contract(file_name: str, *, directory: Optional[Path] = None) -> str:
    """
    Return contents of file_name from directory.
    """
    if directory is None:
        directory = CONTRACTS_COMPILED_DIR

    if not directory.exists():
        raise ValueError(f"Directory {directory} does not exist!")

    return (directory / file_name).read_text("utf-8")


def are_entries_list_equal[T](a: List[T], b: List[T]) -> bool:
    """
    Check if two lists of entries are equal no matter the order.

    :param a: List of entries
    :param b: List of entries
    :return: True if equal, False otherwise
    """

    return set(a) == set(b)
