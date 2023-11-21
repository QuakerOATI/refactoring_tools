import string
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
    def __init__(self, tasks=[]):
        self.tasks = deque(tasks)

    def join(self):
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
        return results

    def map(self, func, args):
        self.tasks.extend([partial(func, *a) for a in args])
        return self

    def __enter__(self):
        self.exceptions = []
        return self.join()

    def __exit__(self, exc_type, exc_val, traceback):
        if isinstance(exc_val, Exception):
            self.exceptions.append(exc_val)
        if self.exceptions:
            raise ExceptionGroup(
                "Exception stack terminated with errors", self.exceptions
            ) from None


class FormatSpecifier:
    """
    %  --> [align]["0"]["#"][width]["." precision]type
    {} --> [[fill]align][sign]["z"]["#"]["0"][width][grouping]["." precision][type]
    """

    class FormatSpecifierError(Exception):
        pass

    def __init__(
        self,
        align=None,
        fill=None,
        numeric_flags=None,
        width=None,
        precision=None,
        display_type="string",
        exc_mode="warn",
    ):
        self.align = "" if align is None else str(align)
        # TODO: Add warning for multicaracter fill
        self.fill = "" if fill is None else str(fill)
        self.numeric_flags = "" if numeric_flags is None else numeric_flags
        self.width = self._get_integer_as_string(width)
        self.precision = self._get_integer_as_string(precision)
        self.display_type = "" if display_type is None else display_type
        if self.precision:
            self.precision = f".{self.precision}"

    def _get_integer_as_string(self, obj):
        if obj is None or obj == "":
            return ""
        else:
            try:
                return str(int(obj))
            except Exception as e:
                raise self.FormatSpecifierError(
                    f"Failed to convert object to integer: {obj}"
                ) from e

    def to_percent(self):
        get_percent_opt = partial(self._get_opt_specifier, "%")
        with ExceptionStack().map(
            get_percent_opt,
            [("align", self.align), ("type", self.display_type)],
        ).map(
            get_percent_opt,
            [("numeric_flags", f) for f in self.numeric_flags],
        ) as (
            align,
            display_type,
            *numeric_flags,
        ):
            if self.fill:
                raise self.FormatSpecifierError(
                    "Cannot specify fill character in printf-style template string"
                )
            fmt = f"%{align}{''.join(numeric_flags)}{self.width}{self.precision}{display_type}"
            self._test("%", fmt)
            return fmt

    def to_brace(self):
        get_brace_opt = partial(self._get_opt_specifier, "{}")
        with ExceptionStack().map(
            get_brace_opt,
            [("align", self.align), ("type", self.display_type)],
        ).map(
            get_brace_opt,
            [("numeric_flags", f) for f in self.numeric_flags],
        ) as (
            align,
            display_type,
            *numeric_flags,
        ):
            if self.fill and not align:
                raise self.FormatSpecifierError(
                    "Fill character can only be defined with a valid alignment specifier"
                )
            convert, display = display_type
            fmt = f":{self.fill[0]}{align}{''.join(numeric_flags)}{self.width}{self.precision}{display}"
            if convert:
                fmt = f"!{convert}{fmt}"
            fmt = "{" + fmt + "}"
            self._test("{}", fmt)
            return fmt

    def _get_opt_specifier(self, fmt_type, opt_name, spec_name):
        if fmt_type == "{}":
            table = BRACE_FORMAT_OPTS
        elif fmt_type == "%":
            table = PERCENT_FORMAT_OPTS
        else:
            raise self.FormatSpecifierError(
                f"Unsupported format specifier type {fmt_type}"
            )
        try:
            table = table[opt_name]
        except KeyError:
            raise self.FormatSpecifierError(
                f"Invalid option '{opt_name}' for format specifier type '{fmt_type}'"
            ) from None
        try:
            return table[spec_name]
        except KeyError:
            raise self.FormatSpecifierError(
                f"Invalid option specifier '{spec_name}' for option '{opt_name}', format specifier type '{fmt_type}'"
            ) from None

    @staticmethod
    def get_brace_fields(s):
        return list(string._string.formatter_parser(s))

    def _test(self, fmt_type, fmt):
        pass
