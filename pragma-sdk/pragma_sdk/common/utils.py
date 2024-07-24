import inspect
from functools import wraps
from typing import List, TypeVar, Any, Callable

from asgiref.sync import async_to_sync

from pragma_sdk.common.logging import get_pragma_sdk_logger

logger = get_pragma_sdk_logger()

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


def str_to_felt(text: str) -> int:
    """
    Convert a string to a felt.
    WARNING : text is converting to uppercase
    """
    if text.upper() != text:
        text = text.upper()
    b_text = bytes(text, "utf-8")
    return int.from_bytes(b_text, "big")


def felt_to_str(felt: int) -> str:
    """
    Convert a felt to a string.
    """
    num_bytes = (felt.bit_length() + 7) // 8
    bytes_ = felt.to_bytes(num_bytes, "big")
    return bytes_.decode("utf-8")


def currency_pair_to_pair_id(base: str, quote: str) -> str:
    """
    Return a pair id from base and quote currencies.
    e.g currency_pair_to_pair_id("btc", "usd") -> "BTC/USD"

    :param base: Base currency
    :param quote: Quote currency
    :return: Pair id
    """

    return f"{base}/{quote}".upper()


def get_cur_from_pair(asset: str) -> List[str]:
    """
    Get the currency from a pair.
    e.g get_cur_from_pair("BTC/USD") -> ["BTC", "USD"]

    :param asset: Asset pair
    :return: List of currencies
    """
    return asset.split("/")


def make_sync(fn: F) -> Callable[..., Any]:
    sync_fun = async_to_sync(fn)

    @wraps(fn)
    def impl(*args: Any, **kwargs: Any) -> Any:
        return sync_fun(*args, **kwargs)

    return impl


def add_sync_methods(original_class: T) -> T:
    """
    Decorator for adding a synchronous version of a class.
    :param original_class: Input class
    :return: Input class with .sync property that contains synchronous version of this class
    """
    properties = {**original_class.__dict__}
    for name, value in properties.items():
        sync_name = name + "_sync"

        # Handwritten implementation exists
        if sync_name in properties:
            continue

        # Make all callables synchronous
        if inspect.iscoroutinefunction(value):
            setattr(original_class, sync_name, make_sync(value))
            _set_sync_method_docstring(original_class, sync_name)
        elif isinstance(value, staticmethod) and inspect.iscoroutinefunction(
            value.__func__
        ):
            setattr(original_class, sync_name, staticmethod(make_sync(value.__func__)))
            _set_sync_method_docstring(original_class, sync_name)
        elif isinstance(value, classmethod) and inspect.iscoroutinefunction(
            value.__func__
        ):
            setattr(original_class, sync_name, classmethod(make_sync(value.__func__)))

    return original_class


def _set_sync_method_docstring(original_class: Any, sync_name: str) -> None:
    sync_method = getattr(original_class, sync_name)
    sync_method.__doc__ = "Synchronous version of the method."
