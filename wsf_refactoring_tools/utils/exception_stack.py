from __future__ import annotations

from collections import deque
from contextlib import AbstractContextManager
from functools import partial
from typing import Any, Callable, List, Tuple


class ExceptionStack(AbstractContextManager):
    """Accumulate exceptions over a series of tasks.

    Methods:
        join: execute tasks and return results, aggregating any exceptions into
            an ExceptionGroup
        map: extend the list of tasks by mapping a function over a list of
            argument tuples
        resolve: combine cached exceptions into an ExceptionGroup and raise
    """

    def __init__(self, tasks: List[Callable[[], Any]] = []) -> None:
        """ExceptionGroup constructor.

        Args:
            tasks: list of callables to be executed (additional tasks can be
                added after initialization)
        """
        self.tasks = deque(tasks)
        self.exceptions = []

    def join(self) -> List[Any]:
        """Execute pending tasks and return the list of return values.

        Tasks that fail to return correspond to values of None in the list of
        results.

        Exceptions thrown by individual tasks are caught, annotated with the
        index of self.tasks at which they were raised, and appended to
        self.exceptions.

        This method is wrapped by ExceptionStack.__enter__, allowing it to be
        used as a context manager.  For example:

        >>> with ExceptionStack(tasks) as results:
        ...     # do something with results
        ...     # all tasks are guaranteed to execute

        When using an ExceptionStack this way, self.exceptions is aggregated
        into an ExceptionGroup and reraised upon exiting the context.

        Returns:
            list of values returned by tasks in self.tasks
        """
        results = []
        while self.tasks:
            task = self.tasks.popleft()
            try:
                results.append(task())
            except Exception as e:
                e.add_note(
                    f"Exception occurred in task index {len(results)} of Exception Stack"
                )
                self.exceptions.append(e)
                results.append(None)
        return results

    def resolve(self) -> None:
        """Resolve exceptions by combining into an ExceptionGroup and raising.

        This method is called by ExceptionStack.__exit__, so it is not
        necessary to call it again when using ExceptionStack as a context
        manager.

        Raises:
            ExceptionGroup
        """
        if self.exceptions:
            raise ExceptionGroup(
                "Exception stack terminated with errors", self.exceptions
            ) from None

    def map(self, func: Callable[[...], Any], args: List[Tuple[Any]]) -> ExceptionStack:
        """Add tasks to self by mapping a function over a list of tuples.

        Args:
            func: function to be mapped
            args: list of tuples to which func should be applied
        Returns:
            self (to allow method-chaining)
        """
        self.tasks.extend([partial(func, *a) for a in args])
        return self

    def __enter__(self):
        return self.join()

    def __exit__(self, exc_type, exc_val, traceback):
        # If an exception is raised outside of individual tasks, append it here
        if isinstance(exc_val, Exception):
            self.exceptions.append(exc_val)
        self.resolve()
