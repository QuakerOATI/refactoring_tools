import string
from collections import deque
from contextlib import AbstractContextManager


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
        "left": "-",
        "right": "",
    },
    "numeric_flags": {
        "alternate_form": "#",
        "pad_zeros": "0",
        "negative_signed": "",
        "always_signed": "+",
        "negative_signed_aligned": " ",
    },
    "type": {
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
        "left": "<",
        "right": ">",
        "center": "^",
        "sign_on_left": "=",
    },
    "numeric_flags": {
        "alternate_form": "#",
        "pad_zeros": "0",
        "float_positive_zero": "z",
        "alternate_form": "#",
        "group_commas": ",",
        "group_underscores": "_",
        "negative_signed": "-",
        "always_signed": "+",
        "negative_signed_aligned": " ",
    },
    "type": {
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
        ct = 0
        while self.tasks:
            task = self.tasks.popleft()
            ct += 1
            try:
                yield task()
            except Exception as e:
                e.add_note(f"Exception occurred in task {ct} of Exception Stack")
                self.exceptions.append(e)
                yield None

    def get_results(self):
        return list(self.join())

    def map(self, func, args):
        self.tasks.extend([lambda: func(*a) for a in args])
        return self

    def __enter__(self):
        self.exceptions = []
        return self.get_results()

    def __exit__(self, exc_type, exc_val, traceback):
        self.exceptions.append(exc_val)
        raise ExceptionGroup("Exception stack terminated with errors", self.exceptions)


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
        type="s",
        exc_mode="warn",
    ):
        self.align = "" if align is None else str(align)
        # TODO: Add warning for multicaracter fill
        self.fill = "" if fill is None else str(fill)
        self.numeric_flags = "" if numeric_flags is None else numeric_flags
        self.width = self._get_integer_as_string(width)
        self.precision = self._get_integer_as_string(precision)
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
        with ExceptionStack().map(
            self._get_percent_opt_specifier,
            [("align", self.align), ("fill", self.fill), ("type", self.type)],
        ).map(
            self._get_percent_opt_specifier,
            [("numeric_flags", f) for f in self.numeric_flags],
        ) as (
            align,
            fill,
            display_type,
            *numeric_flags,
        ):
            if fill:
                raise self.FormatSpecifierException(
                    "Cannot specify fill character in printf-style template string"
                )
            fmt = f"%{align}{''.join(numeric_flags)}{self.width}{self.precision}{display_type}"
            self._test("%", fmt)
            return fmt

    def to_brace(self):
        with ExceptionStack().map(
            self._get_percent_opt_specifier,
            [("align", self.align), ("fill", self.fill), ("type", self.type)],
        ).map(
            self._get_percent_opt_specifier,
            [("numeric_flags", f) for f in self.numeric_flags],
        ) as (
            align,
            fill,
            display_type,
            *numeric_flags,
        ):
            if fill and not align:
                raise self.FormatSpecifierException(
                    "Fill character must be defined with an alignment specifier"
                )
            convert, display = display_type
            fmt = f":{fill}{align}{''.join(numeric_flags)}{self.width}{self.precision}{display}"
            if convert:
                fmt = f"!{convert}{fmt}"
            fmt = "{" + fmt + "}"
            self._test("{}", fmt)
            return fmt

    def _get_brace_opt_specifier(self, opt_name, spec_name):
        try:
            opt_table = BRACE_FORMAT_OPTS[opt_name]
        except KeyError:
            raise self.FormatSpecifierError(f"Invalid option name {opt_name}") from None
        try:
            return opt_table[spec_name]
        except KeyError:
            raise self.FormatSpecifierError(
                f"Invalid specifier name {spec_name} for option {opt_name}"
            )

    def _get_percent_opt_specifier(self, opt_name, spec_name):
        try:
            opt_table = PERCENT_FORMAT_OPTS[opt_name]
        except KeyError:
            raise self.FormatSpecifierError(f"Invalid option name {opt_name}") from None
        try:
            return opt_table[spec_name]
        except KeyError:
            raise self.FormatSpecifierError(
                f"Invalid specifier name {spec_name} for option {opt_name}"
            )

    @staticmethod
    def get_brace_fields(s):
        return list(string._string.formatter_parser(s))
