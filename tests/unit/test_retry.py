"""Unit tests for retry decorator with exponential backoff.

This module tests the retry_with_backoff decorator to ensure it correctly
implements exponential backoff and retry logic.
"""

import time
from unittest.mock import Mock

import pytest

from src.retry import retry_with_backoff


class TestRetryWithBackoff:
    """Test suite for retry_with_backoff decorator."""

    def test_successful_first_attempt(self):
        """Test that a successful function call on first attempt returns immediately."""
        mock_func = Mock(return_value="success")
        decorated = retry_with_backoff(max_retries=3, backoff_base=2.0)(mock_func)

        result = decorated()

        assert result == "success"
        assert mock_func.call_count == 1

    def test_successful_after_retries(self):
        """Test that function succeeds after some failures."""
        mock_func = Mock(side_effect=[ValueError("fail1"), ValueError("fail2"), "success"])
        decorated = retry_with_backoff(max_retries=3, backoff_base=2.0, exceptions=ValueError)(
            mock_func
        )

        result = decorated()

        assert result == "success"
        assert mock_func.call_count == 3

    def test_max_retries_exceeded(self):
        """Test that exception is raised after max retries exceeded."""
        mock_func = Mock(side_effect=ValueError("persistent failure"))
        decorated = retry_with_backoff(max_retries=2, backoff_base=2.0, exceptions=ValueError)(
            mock_func
        )

        with pytest.raises(ValueError, match="persistent failure"):
            decorated()

        # Should be called: initial attempt + 2 retries = 3 times
        assert mock_func.call_count == 3

    def test_exponential_backoff_timing(self):
        """Test that exponential backoff delays are applied correctly."""
        call_times = []

        def failing_func():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise ValueError("fail")
            return "success"

        decorated = retry_with_backoff(max_retries=3, backoff_base=2.0, exceptions=ValueError)(
            failing_func
        )

        result = decorated()

        assert result == "success"
        assert len(call_times) == 3

        # Check delays between attempts
        # First retry delay: 2^0 = 1 second
        # Second retry delay: 2^1 = 2 seconds
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]

        # Allow some tolerance for timing (±0.1 seconds)
        assert 0.9 <= delay1 <= 1.1, f"First delay should be ~1s, got {delay1:.2f}s"
        assert 1.9 <= delay2 <= 2.1, f"Second delay should be ~2s, got {delay2:.2f}s"

    def test_specific_exception_types(self):
        """Test that only specified exception types are retried."""
        mock_func = Mock(side_effect=RuntimeError("wrong exception"))
        decorated = retry_with_backoff(max_retries=3, backoff_base=2.0, exceptions=ValueError)(
            mock_func
        )

        # RuntimeError should not be caught and retried
        with pytest.raises(RuntimeError, match="wrong exception"):
            decorated()

        # Should only be called once (no retries for unspecified exceptions)
        assert mock_func.call_count == 1

    def test_multiple_exception_types(self):
        """Test that multiple exception types can be specified for retry."""
        mock_func = Mock(side_effect=[ValueError("fail1"), RuntimeError("fail2"), "success"])
        decorated = retry_with_backoff(
            max_retries=3, backoff_base=2.0, exceptions=(ValueError, RuntimeError)
        )(mock_func)

        result = decorated()

        assert result == "success"
        assert mock_func.call_count == 3

    def test_on_retry_callback(self):
        """Test that on_retry callback is called on each retry attempt."""
        callback_calls = []

        def on_retry_callback(exception: Exception, attempt: int):
            callback_calls.append((str(exception), attempt))

        mock_func = Mock(side_effect=[ValueError("fail1"), ValueError("fail2"), "success"])
        decorated = retry_with_backoff(
            max_retries=3, backoff_base=2.0, exceptions=ValueError, on_retry=on_retry_callback
        )(mock_func)

        result = decorated()

        assert result == "success"
        assert len(callback_calls) == 2  # Called on first and second retry
        assert callback_calls[0] == ("fail1", 1)
        assert callback_calls[1] == ("fail2", 2)

    def test_on_retry_callback_exception_handling(self):
        """Test that exceptions in on_retry callback don't break retry logic."""

        def failing_callback(exception: Exception, attempt: int):
            raise RuntimeError("callback error")

        mock_func = Mock(side_effect=[ValueError("fail1"), "success"])
        decorated = retry_with_backoff(
            max_retries=3, backoff_base=2.0, exceptions=ValueError, on_retry=failing_callback
        )(mock_func)

        # Should still succeed despite callback failure
        result = decorated()
        assert result == "success"

    def test_zero_max_retries(self):
        """Test that max_retries=0 means no retries (only initial attempt)."""
        mock_func = Mock(side_effect=ValueError("fail"))
        decorated = retry_with_backoff(max_retries=0, backoff_base=2.0, exceptions=ValueError)(
            mock_func
        )

        with pytest.raises(ValueError, match="fail"):
            decorated()

        # Should only be called once (no retries)
        assert mock_func.call_count == 1

    def test_function_with_arguments(self):
        """Test that decorated function correctly passes arguments."""

        def add_numbers(a: int, b: int, c: int = 0) -> int:
            return a + b + c

        decorated = retry_with_backoff(max_retries=3, backoff_base=2.0)(add_numbers)

        result = decorated(1, 2, c=3)
        assert result == 6

    def test_function_preserves_name_and_docstring(self):
        """Test that decorator preserves function metadata."""

        def my_function():
            """This is my function."""
            return "result"

        decorated = retry_with_backoff(max_retries=3, backoff_base=2.0)(my_function)

        assert decorated.__name__ == "my_function"
        assert decorated.__doc__ == "This is my function."

    def test_different_backoff_base(self):
        """Test that different backoff base values work correctly."""
        call_times = []

        def failing_func():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise ValueError("fail")
            return "success"

        # Use backoff_base=3.0 instead of 2.0
        decorated = retry_with_backoff(max_retries=3, backoff_base=3.0, exceptions=ValueError)(
            failing_func
        )

        result = decorated()

        assert result == "success"
        assert len(call_times) == 3

        # Check delays between attempts
        # First retry delay: 3^0 = 1 second
        # Second retry delay: 3^1 = 3 seconds
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]

        # Allow some tolerance for timing
        assert 0.9 <= delay1 <= 1.1, f"First delay should be ~1s, got {delay1:.2f}s"
        assert 2.9 <= delay2 <= 3.1, f"Second delay should be ~3s, got {delay2:.2f}s"

    def test_large_max_retries(self):
        """Test that large max_retries value is handled correctly."""
        mock_func = Mock(side_effect=[ValueError("fail")] * 5 + ["success"])
        decorated = retry_with_backoff(max_retries=10, backoff_base=2.0, exceptions=ValueError)(
            mock_func
        )

        result = decorated()

        assert result == "success"
        assert mock_func.call_count == 6  # 5 failures + 1 success
