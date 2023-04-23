from builtins import map as _builtins_map
from concurrent.futures import Executor


class NaiveExecutor(Executor):
    def map(self, func, *iterables, timeout=None, chunksize=1):
        return _builtins_map(func, *iterables)

    # no, this is not a complete implementation
