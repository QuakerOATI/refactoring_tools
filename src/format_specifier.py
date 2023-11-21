# coding: utf-8
class FormatSpecifier:
    """
    %  --> [align]["0"]["#"][width]["." precision]type
    {} --> [[fill]align][sign]["z"]["#"]["0"][width][grouping]["." precision][type]
    """
    PERCENT_CONVERSION_TYPES = {
        "d": "decimal_integer",
        "i": "integer",
        "u": "unsigned_integer",
        "x": "hex_lowercase",
        "X": "hex_uppercase",
        "o": "octal",
        "f": "fixed_point_lowercase",
        "F": "fixed_point_uppercase",
        "e": "scientific_lowercase",
        "E": "scientific_uppercase",
        "g": "general_format_lowercase",
        "G": "general_format_uppercase",
        "c": "character",
        "s": "string",
        "r": "repr",
        "a": "ascii",
    }
    BRACE_PRESENTATION_TYPES = {
        None: "string",
        "s": "string",
        "b": "binary",
        "c": "character",
        "d": "decimal",
        "o": "octal",
        "x": "hex_lowercase",
        "X": "hex_uppercase",
        "n": "decimal_localized",
        "e": "scientific_lowercase",
        "E": "scientific_uppercase",
        "f": "fixed_point_lowercase",
        "F": "fixed_point_uppercase",
        "g": "general_format_lowercase",
        "G": "general_format_uppercase",
        "%": "percentage",
    }
    BRACE_CONVERSION_FLAGS = {
        "s": "string",
        "a": "ascii",
        "r": "repr",
    }
    def __init__(self, align="right", fill=" ", sign=None, coerce_positive=False, alternate_numeric_form=False, width=None, precision=None, type="s"):
        if align not in ("left", "right", "center", "="):
            raise self.FormatSpecifierError(f"Bad alignment: {align}")
        self.align = align
        self.fill = fill
        if sign not in "+", "-", " ":
            raise self.FormatSpecifierError(f"Bad sign: {sign}")
        self.sign = sign
        self.coerce_positive = coerce_positive
        self.alternate_numeric_form = alternate_numeric_form
        self.width = self._get_integer_as_string(width)
        self.precision = self._get_integer_as_string(precision)
                        
    def _get_integer_as_string(self, obj):
        if obj is None or obj == "":
            return ""
        else:
            try:
                return str(int(obj))
            except Exception as e:
                raise self.FormatSpecifierError(f"Failed to convert object to integer: {obj}") from e
                
    class FormatSpecifierError(Exception):
        pass
    def to_percent(self):
        if self.fill_char:
            raise FormatSpecifierError("Percent format strings do not allow arbitrary fill characters")
        return '%' + self.alignment('%')
    @staticmethod
    def get_brace_fields(s):
        return list(string._string.formatter_parser(s))
        
