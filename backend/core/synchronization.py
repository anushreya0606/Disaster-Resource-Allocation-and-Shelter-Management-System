import threading
from contextlib import contextmanager


class AllocationLock:
    """
    Provides a lock for shelter allocation operations.

    This prevents multiple threads in the same application
    process from modifying allocation-related state at the
    same time.
    """

    def __init__(self):
        self._lock = threading.Lock()

    @contextmanager
    def acquire(self):
        """
        Acquire the lock and release it automatically
        when the operation is finished.
        """

        self._lock.acquire()

        try:
            yield
        finally:
            self._lock.release()


# Shared lock for allocation operations within this process.
allocation_lock = AllocationLock()