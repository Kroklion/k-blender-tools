import time
import functools
from contextlib import contextmanager

"""
Timing Utilities
================

This module provides lightweight tools to measure execution times and count
calls for functions, code blocks, and arbitrary events. It is designed as a
simpler alternative to full profilers when you just want cumulative timings
and counts.

Features
--------
- @timed decorator: measure execution time of functions and methods.
- timed_block(label): context manager to measure arbitrary code blocks.
- timed_measure_start/stop(label): manual start/stop timing.
- timed_increment(label): increment a counter without timing (e.g. for events).
- timed_print(): print a formatted table of collected stats.
- timed_reset(): clear all collected stats.

Data Model
----------
All stats are stored in a dictionary mapping a label (function name or custom
string) to a tuple:

    (total_time_in_seconds, call_count)

Usage Examples
--------------

1. Decorating functions:

    from timing_utils import timed, timed_print

    @timed
    def slow_function():
        time.sleep(0.2)

    slow_function()
    slow_function()
    timed_print()

    # Output:
    # Collected execution stats:
    # slow_function |   Calls | Total Time (s) | Avg Time (s)
    # -------------------------------------------------------
    # __main__.slow_function |       2 |        0.400123 |     0.200061

2. Timing code blocks:

    from timing_utils import timed_block

    with timed_block("processing"):
        do_work()

3. Manual start/stop:

    from timing_utils import timed_measure_start, timed_measure_stop

    timed_measure_start("searching")
    search_objects()
    timed_measure_stop("searching")

4. Counting events:

    from timing_utils import timed_increment

    for item in items:
        if item.is_valid():
            timed_increment("valid items")

5. Resetting stats:

    from timing_utils import timed_reset

    timed_reset()  # clears all collected times and counts

Notes
-----
- Labels are automatically generated for decorated functions using
  "<module>.<qualname>".
- For manual blocks and increments, you can choose any string label.
- Use timed_print() to see a summary with total time, call count, and average.
"""

# Dictionary to store accumulated stats per function/label
# Each entry: name -> (total_time, count)
_function_stats = {}

# Temporary storage for manual measurements
_active_measurements = {}


def _ensure_entry(name: str):
    """Ensure that a stats entry exists for the given name."""
    if name not in _function_stats:
        _function_stats[name] = (0.0, 0)


def _update_stats(name: str, elapsed: float = 0.0, increment: int = 1):
    """Update stats for a given name with elapsed time and count increment."""
    _ensure_entry(name)
    total_time, count = _function_stats[name]
    _function_stats[name] = (total_time + elapsed, count + increment)


def timed(func):
    """Decorator that measures execution time and accumulates it per function."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start

        name = f"{func.__module__}.{func.__qualname__}"
        _update_stats(name, elapsed)
        return result
    return wrapper


def timed_reset():
    """Reset all collected stats."""
    _function_stats.clear()
    _active_measurements.clear()


def timed_measure_start(label: str):
    """Start a manual measurement with a given label."""
    _active_measurements[label] = time.perf_counter()


def timed_measure_stop(label: str):
    """Stop a manual measurement and accumulate the elapsed time under the label."""
    if label not in _active_measurements:
        raise ValueError(f"No active measurement for label '{label}'")
    start = _active_measurements.pop(label)
    elapsed = time.perf_counter() - start
    _update_stats(label, elapsed)


@contextmanager
def timed_block(label: str):
    """Context manager to measure execution time of a code block."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        _update_stats(label, elapsed)


def timed_increment(label: str):
    """Increment only the call count for a given label (no timing)."""
    _update_stats(label, 0.0, 1)


def timed_print():
    """Print the collected execution times and counts."""
    if not _function_stats:
        print("No execution times collected.")
        return

    max_len = max(len(name) for name in _function_stats)

    print("Collected execution stats:")
    print(f"{'Name':<{max_len}} | {'Calls':>7} | {'Total Time (s)':>14} | {'Avg Time (s)':>12}")
    print("-" * (max_len + 42))

    for name, (total_time, count) in _function_stats.items():
        avg_time = total_time / count if count else 0.0
        print(f"{name:<{max_len}} | {count:7d} | {total_time:14.6f} | {avg_time:12.6f}")
