import string
import dataclasses
from abc import ABC
from __future__ import annotations
from typing import List, Callable, Tuple, Literal, TypeVar, Union
from collections import deque
from contextlib import AbstractContextManager
from functools import partial

NUMERIC_TYPES = [
    "decimal",
    "integer",
    "unsigned_integer",
    "hex_lowercase",
    "hex_uppercase",
    "octal",
    "fixed_point_lowercase",
    "fixed_point_uppercase",
    "general_format_lowercase",
    "general_format_uppercase",
    "binary",
    "percentage",
    "decimal_localized",
]

NONNUMERIC_TYPES = [
    "string",
    "repr",
    "ascii",
    "char",
]

PERCENT_FORMAT_OPTS = {
    "align": {
        "": "",
        "left": "-",
        "right": "",
    },
    "numeric_flags": {
        "": "",
        "alternate_form": "#",
        "pad_zeros": "0",
        "negative_signed": "",
        "always_signed": "+",
        "negative_signed_aligned": " ",
    },
    "type": {
        "": "s",
        "decimal": "d",
        "integer": "i",
        "unsigned_integer": "u",
        "hex_lowercase": "x",
        "hex_uppercase": "X",
        "octal": "o",
        "fixed_point_lowercase": "f",
        "fixed_point_uppercase": "F",
        "scientific_lowercase": "e",
        "scientific_uppercase": "E",
        "general_format_lowercase": "g",
        "general_format_uppercase": "G",
        "character": "c",
        "string": "s",
        "repr": "r",
        "ascii": "a",
    },
}

BRACE_FORMAT_OPTS = {
    "align": {
        "": "",
        "left": "<",
        "right": ">",
        "center": "^",
        "sign_on_left": "=",
    },
    "numeric_flags": {
        "": "",
        "alternate_form": "#",
        "pad_zeros": "0",
        "float_positive_zero": "z",
        "group_commas": ",",
        "group_underscores": "_",
        "negative_signed": "-",
        "always_signed": "+",
        "negative_signed_aligned": " ",
    },
    "type": {
        "": "s",
        "binary": ("", "b"),
        "decimal": ("", "d"),
        "integer": ("", "i"),
        "hex_lowercase": ("", "x"),
        "hex_uppercase": ("", "X"),
        "octal": ("", "o"),
        "fixed_point_lowercase": ("", "f"),
        "fixed_point_uppercase": ("", "F"),
        "scientific_lowercase": ("", "e"),
        "scientific_uppercase": ("", "E"),
        "general_format_lowercase": ("", "g"),
        "general_format_uppercase": ("", "G"),
        "character": ("", "c"),
        "string": ("s", "s"),
        "repr": ("r", "s"),
        "ascii": ("a", "s"),
        "percentage": ("", "%"),
        "decimal_localized": ("", "n"),
    },
}


class ExceptionStack(AbstractContextManager):
    """Accumulate exceptions over a series of tasks.

    Methods:
        join: execute tasks and return results, aggregating any exceptions into
            an ExceptionGroup
        map: extend the list of tasks by mapping a function over a list of
            argument tuples
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
        >>>     # do something with results
        >>>     # all tasks are guaranteed to execute

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
            raise ExceptionGroup("Exception stack terminated with errors",
                                 self.exceptions) from None

    def map(self, func: Callable[[...], Any],
            args: List[Tuple[Any]]) -> ExceptionStack:
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
        # If an exceptions is raised outside of individual tasks, append it here
        if isinstance(exc_val, Exception):
            self.exceptions.append(exc_val)
        self.resolve()


@dataclasses.dataclass
class NumericFormat:
    alternate_form: bool = False
    pad_zeros: bool = False
    float_positive_zero: Optional[bool] = False
    group: Optional[Literal["comma", "underscore"]] = None
    sign: Literal["sign_positive", "nosign_positive",
                  "align_positive"] = "nosign_positive"
    justifySign: Optional[bool] = None
    precision: Optional[int] = None


@dataclasses.dataclass
class AlignmentFormat:
    justify: Literal["left", "right", "center"] = "right"
    fill: Optional[str] = None
    width: Optional[int] = None


NumericType: TypeVar = Literal[*NUMERIC_TYPES]
NonnumericType: TypeVar = Literal[*NONNUMERIC_TYPES]
TypeFormat: TypeVar = Union[NumericType, NonnumericType]


class FormatSpecifier(ABC):

    def __init__(self, alignmentFormat: AlignmentFormat,
                 numericFormat: NumericFormat, typeFormat: TypeFormat) -> None:
        self.alignmentFormat = alignmentFormat
        self.numericFormat = numericFormat
        self.typeFormat = typeFormat
        self.validate()

    def validate_typeFormat(self):
        if self.typeFormat in NONNUMERIC_TYPES:
            assert self.numericFormat == NumericFormat(
            ), "Numeric format options cannot be specified for non-numeric types"
        else:
            assert self.numericFormat in NUMERIC_TYPES, f"Invalid type format '{self.numericFormat}'"

    def validate(self) -> None:
        validation_methods = [
            attr for name in dir(self) if callable(
                attr := getattr(self, name)) and name.startswith("validate_")
        ]
        with ExceptionStack(validation_methods):
            pass

    @abstractmethod
    def __repr__(self):
        ...


class PercentFormatSpecifier(FormatSpecifier):

    JUSTIFY = {
        "left": "-",
        "right": "",
    }

    SIGN = {"sign_positive": "+", "nosign_positive": "", "align_positive": " "}

    def __repr__(self):
        fmt = self.SIGN[self.numericFormat.sign]
        fmt += self.JUSTIFY[self.alignmentFormat.justify]
        if self.numericFormat.pad_zeros:
            fmt += "0"
        if self.numericFormat.alternate_form:
            fmt += "#"
        if self.alignmentFormat.width:
            fmt += str(self.alignmentFormat.width)
        if self.numericFormat.precision:
            fmt += f".{self.numericFormat.precision}"
        fmt += self.typeFormat
        return f"%{fmt}"


class BraceFormatSpecifier(FormatSpecifier):

    JUSTIFY = {
        "left": "<",
        "right": ">",
        "center": "^",
    }

    SIGN = {
        "sign_positive": "+",
        "nosign_positive": "-",
        "align_positive": " ",
    }

    GROUP = {"comma": ",", "underscore": "_"}

    def __repr__(self):
        fmt += self.SIGN[self.numericFormat.sign]
        fmt = self.JUSTIFY[self.alignmentFormat.justify]
        if self.alignmentFormat.fill:
            fmt = str(fill)[0] + fmt
        if self.numericFormat.float_positive_zero:
            fmt += "z"
        if self.numericFormat.alternate_form:
            fmt += "#"
        if self.numericFormat.pad_zeros:
            fmt += "0"
        if self.alignmentFormat.width:
            fmt += str(self.alignmentFormat.width)
        if self.numericFormat.group:
            fmt += self.GROUP[self.numericFormat.group]
        if self.numericFormat.precision:
            fmt += f".{self.numericFormat.precision}"
        fmt += self.typeFormat
        return "{" + fmt + "}"
