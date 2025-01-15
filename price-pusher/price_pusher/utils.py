from typing import List, Union, Optional, TypeVar

from pragma_sdk.offchain.client import PragmaAPIError

T = TypeVar("T")


def exclude_none_and_exceptions(
    to_filter: List[Optional[Union[T, BaseException, Exception, PragmaAPIError]]],
) -> List[T]:
    """
    Remove exceptions and none from a list of items.
    """
    exception_types = (type(None), BaseException, Exception, PragmaAPIError)
    return [item for item in to_filter if not isinstance(item, exception_types)]


def flatten_list(to_flatten: List[Union[T, List[T]]]) -> List[T]:
    """
    Flatten a list that contains items and list of items into a list of items.
    """
    return [
        val
        for item in to_flatten
        for val in (item if isinstance(item, (list, tuple)) else [item])
    ]
