"""Retry decorator with exponential backoff for error handling.

This module provides a retry decorator that implements exponential backoff
for handling transient failures in network operations and device communication.
"""

import functools
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

# Type variable for generic function return type
F = TypeVar("F", bound=Callable[..., Any])


def retry_with_backoff(
    max_retries: int = 10,
    backoff_base: float = 2.0,
    exceptions: type[Exception] | tuple[type[Exception], ...] = Exception,
    on_retry: Callable[[Exception, int], None] | None = None,
) -> Callable[[F], F]:
    """Decorator that retries a function with exponential backoff.

    This decorator implements a retry mechanism with exponential backoff for
    handling transient failures. The delay between retries increases exponentially
    according to the formula: delay = backoff_base^attempt

    Args:
        max_retries: Maximum number of retry attempts (default: 10)
        backoff_base: Base for exponential backoff calculation (default: 2.0)
        exceptions: Exception type(s) to catch and retry (default: Exception)
        on_retry: Optional callback function called on each retry attempt,
                 receives the exception and attempt number

    Returns:
        Decorated function that implements retry logic

    Example:
        @retry_with_backoff(max_retries=5, backoff_base=2.0)
        def connect_to_device():
            # Connection logic that may fail
            pass

    Requirements: 8.2, 8.5
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None
            func_name = getattr(func, "__name__", repr(func))

            # Attempt the function call up to max_retries + 1 times
            # (initial attempt + max_retries retries)
            for attempt in range(max_retries + 1):
                try:
                    # Attempt to call the function
                    result = func(*args, **kwargs)
                    return result

                except exceptions as e:
                    last_exception = e

                    # If this was the last attempt, raise the exception
                    if attempt >= max_retries:
                        logger.error(
                            f"Function {func_name} failed after {max_retries} retries: {e}"
                        )
                        raise

                    # Calculate exponential backoff delay (Requirement 8.2)
                    # delay = base^attempt
                    delay = backoff_base**attempt

                    logger.warning(
                        f"Function {func_name} failed "
                        f"(attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )

                    # Call the on_retry callback if provided
                    if on_retry is not None:
                        try:
                            on_retry(e, attempt + 1)
                        except Exception as callback_error:
                            logger.error(f"Error in on_retry callback: {callback_error}")

                    # Wait before retrying (Requirement 8.2)
                    time.sleep(delay)

            # This should never be reached, but just in case
            if last_exception is not None:
                raise last_exception
            else:
                raise RuntimeError(f"Function {func_name} failed with unknown error")

        return wrapper  # type: ignore

    return decorator


def retry_with_backoff_async(
    max_retries: int = 10,
    backoff_base: float = 2.0,
    exceptions: type[Exception] | tuple[type[Exception], ...] = Exception,
    on_retry: Callable[[Exception, int], None] | None = None,
) -> Callable[[F], F]:
    """Async version of retry_with_backoff decorator.

    This decorator implements the same retry mechanism as retry_with_backoff
    but for async functions. It uses asyncio.sleep instead of time.sleep.

    Args:
        max_retries: Maximum number of retry attempts (default: 10)
        backoff_base: Base for exponential backoff calculation (default: 2.0)
        exceptions: Exception type(s) to catch and retry (default: Exception)
        on_retry: Optional callback function called on each retry attempt,
                 receives the exception and attempt number

    Returns:
        Decorated async function that implements retry logic

    Example:
        @retry_with_backoff_async(max_retries=5, backoff_base=2.0)
        async def connect_to_broker():
            # Async connection logic that may fail
            pass

    Requirements: 8.2, 8.5
    """
    import asyncio

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None
            func_name = getattr(func, "__name__", repr(func))

            # Attempt the function call up to max_retries + 1 times
            for attempt in range(max_retries + 1):
                try:
                    # Attempt to call the async function
                    result = await func(*args, **kwargs)
                    return result

                except exceptions as e:
                    last_exception = e

                    # If this was the last attempt, raise the exception
                    if attempt >= max_retries:
                        logger.error(
                            f"Async function {func_name} failed after {max_retries} retries: {e}"
                        )
                        raise

                    # Calculate exponential backoff delay (Requirement 8.2)
                    delay = backoff_base**attempt

                    logger.warning(
                        f"Async function {func_name} failed "
                        f"(attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )

                    # Call the on_retry callback if provided
                    if on_retry is not None:
                        try:
                            on_retry(e, attempt + 1)
                        except Exception as callback_error:
                            logger.error(f"Error in on_retry callback: {callback_error}")

                    # Wait before retrying (Requirement 8.2)
                    await asyncio.sleep(delay)

            # This should never be reached, but just in case
            if last_exception is not None:
                raise last_exception
            else:
                raise RuntimeError(f"Async function {func_name} failed with unknown error")

        return wrapper  # type: ignore

    return decorator
