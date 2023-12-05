from __future__ import annotations

import dataclasses
import string
from typing import List, Literal, Optional, TypeVar, Union

from exception_stack import ExceptionStack

NUMERIC_TYPES = {
    "decimal": "d",
    "integer": "i",
    "unsigned_integer": "u",
    "hex_lowercase": "x",
    "hex_uppercase": "X",
    "octal": "o",
    "fixed_point_lowercase": "f",
    "fixed_point_uppercase": "F",
    "general_format_lowercase": "g",
    "general_format_uppercase": "G",
    "binary": "b",
    "percentage": "%",
    "decimal_localized": "n",
}

NUMERIC_TYPES_INV = {v: k for k, v in NUMERIC_TYPES.items()}

NONNUMERIC_TYPES = {
    "string": "s",
    "repr": "r",
    "ascii": "a",
    "char": "c",
}

NONNUMERIC_TYPES_INV = {v: k for k, v in NONNUMERIC_TYPES.items()}


@dataclasses.dataclass
class NumericFormat:
    alternate_form: bool = False
    pad_zeros: bool = False
    float_positive_zero: Optional[bool] = False
    group: Optional[Literal["comma", "underscore"]] = None
    sign: Literal[
        "sign_positive", "nosign_positive", "align_positive"
    ] = "nosign_positive"
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


class FormatSpecifier:
    def __init__(
        self,
        alignmentFormat: AlignmentFormat,
        numericFormat: NumericFormat,
        typeFormat: TypeFormat,
        fieldName: Optional[str] = None,
    ) -> None:
        self.alignmentFormat = alignmentFormat
        self.numericFormat = numericFormat
        self.typeFormat = typeFormat
        self.fieldName = fieldName
        self.validate()

    def validate_typeFormat(self):
        if self.typeFormat in NONNUMERIC_TYPES:
            assert (
                self.numericFormat == NumericFormat()
            ), "Numeric format options cannot be specified for non-numeric types"
        else:
            assert (
                self.typeFormat in NUMERIC_TYPES
            ), f"Invalid type format '{self.typeFormat}'"

    def validate(self) -> None:
        validation_methods = [
            attr
            for name in dir(self)
            if callable(attr := getattr(self, name)) and name.startswith("validate_")
        ]
        with ExceptionStack(validation_methods):
            pass

    @classmethod
    def from_spec(cls, specifier: FormatSpecifier):
        return cls(
            alignmentFormat=specifier.alignmentFormat,
            numericFormat=specifier.numericFormat,
            typeFormat=specifier.typeFormat,
            fieldName=specifier.fieldName,
        )

    @classmethod
    def from_text_fields(cls, fields: List[Union[str, FormatSpecifier]]):
        return "".join(list(map(str, fields)))

    def __repr__(self):
        return f"FormatSpecifier(alignment: {self.alignmentFormat}, numeric: {self.numericFormat}, type: {self.typeFormat}, field: {self.fieldName})"


class PercentFormatSpecifier(FormatSpecifier):
    JUSTIFY = {
        "left": "-",
        "right": "",
    }

    SIGN = {"sign_positive": "+", "nosign_positive": "", "align_positive": " "}

    TYPE_UNDEF = ["decimal_localized", "percentage", "binary"]

    def validate_type_defined(self):
        assert (
            self.typeFormat not in self.TYPE_UNDEF
        ), f"Type '{self.typeFormat}' not defined for percent-style format specifiers"

    def __str__(self):
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
        fmt += (NUMERIC_TYPES | NONNUMERIC_TYPES).get(self.typeFormat)
        field_spec = "%"
        if field := self.fieldName:
            field_spec += f"({field})"
        return f"{field_spec}{fmt}"


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

    TYPE_UNDEF = ["char"]

    def validate_type_defined(self):
        assert (
            self.typeFormat not in self.TYPE_UNDEF
        ), f"Type '{self.typeFormat}' not defined for brace-style format specifiers"

    def validate_group(self):
        if self.typeFormat == "decimal_localized":
            assert (
                self.numericFormat.group is None
            ), "Cannot specify a group separator with numeric type '{self.typeFormat}'"

    def __str__(self):
        fmt = self.JUSTIFY[self.alignmentFormat.justify]
        fmt += self.SIGN[self.numericFormat.sign]
        if fill := self.alignmentFormat.fill:
            fmt = str(fill)[0] + fmt
        if self.numericFormat.float_positive_zero:
            fmt += "z"
        if self.numericFormat.alternate_form:
            fmt += "#"
        if self.numericFormat.pad_zeros:
            fmt += "0"
        if width := self.alignmentFormat.width:
            fmt += str(width)
        if group := self.numericFormat.group:
            fmt += self.GROUP[group]
        if precision := self.numericFormat.precision:
            fmt += f".{precision}"
        if self.typeFormat in NONNUMERIC_TYPES:
            fmt = f"!{NONNUMERIC_TYPES[self.typeFormat]}:{fmt}s"
        else:
            fmt = f":{fmt}{NUMERIC_TYPES[self.typeFormat]}"
        if field := self.fieldName:
            fmt = f"{field}{fmt}"
        return "{" + fmt + "}"

    @classmethod
    def _from_formatter_parser_field(cls, field: str):
        text, fieldName, spec, conv = field
        if spec is None:
            return text
        num = NumericFormat()
        align = AlignmentFormat()
        if not conv:
            if spec[-1].isalpha():
                conv = spec[-1]
            else:
                conv = "s"
        typeName = (NUMERIC_TYPES_INV | NONNUMERIC_TYPES_INV)[conv]
        for k, v in cls.JUSTIFY.items():
            if v in spec:
                align.justify = k
                if (idx := spec.find(v)) > 0:
                    align.fill = spec[:idx]
        for k, v in cls.SIGN.items():
            if v in spec:
                num.sign = k
        for k, v in cls.GROUP.items():
            if v in spec:
                num.group = k
        if "z" in spec:
            num.float_positive_zero = True
        if "#" in spec:
            num.alternate_form = True
        if "." in spec:
            num.precision = int(
                "".join([c for c in spec[spec.find(".") :] if c.isnumeric()])
            )
        width = "".join([c for c in spec[: spec.find(".")] if c.isnumeric()])
        if width.startswith("0"):
            num.pad_zeros = True
        if width:
            align.width = int(width)
        return FormatSpecifier(align, num, typeName, fieldName)

    @classmethod
    def from_format_string(cls, fmt: str) -> List[Union[str, FormatSpecifier]]:
        fields = string._string.formatter_parser(fmt)
        return [cls._from_formatter_parser_field(field) for field in fields]
