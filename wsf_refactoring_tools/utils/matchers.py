import libcst as cst
import libcst.matchers as m
from ast import literal_eval
from typing import Tuple, List


LOGLEVELS = ["DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL", "FATAL"]


def LogLevelLiteral():
    """Matcher factory for use with libcst.matchers functions and decorators."""
    # Note that SimpleString.value includes the quotes, so we have to check value[1:-1]
    return m.SimpleString(
        value=m.MatchIfTrue(lambda value: literal_eval(value) in LOGLEVELS)
    )


def TemplateString():
    """Matcher factory for use with libcst.matchers functions and decorators."""
    return m.Call(func=m.Attribute(value=m.SimpleString(), attr=m.Name(value="format")))


def LogFunctionCall():
    """Match against function calls of the form func(msg, ..., LOGLEVEL).

    `msg` is assumed to be either a string literal or a call to str.format();
    LOGLEVEL is assumed to be the string representation of one of the standard
    Python loglevels.
    """
    return m.Call(
        func=m.Name(),
        args=[
            m.Arg(value=TemplateString() | m.SimpleString()),
            m.ZeroOrMore(),
            m.Arg(value=LogLevelLiteral()),
            m.ZeroOrMore(),
        ],
    )


def split_logfunc_args(node: cst.Call) -> Tuple[List[cst.Arg], List[cst.Arg]]:
    fmt, loglevel, filename = None, None, None
    unmatched = []
    for arg in node.args:
        if m.matches(arg, m.Arg(value=LogLevelLiteral())):
            if loglevel is not None:
                raise ValueError("Multiple loglevels found in libcst.Call node on attempt to apply logfunc parsing rules")
            loglevel = arg
        elif m.matches(arg, m.Arg(value=TemplateString())):
            if fmt is not None:
                raise ValueError("Multiple format strings found in libcst.Call node on attempt to apply logfunc parsing rules")
        elif m.matches(arg, m.Arg(value=m.Name("file") | m.Name("File")):
            if filename is not None:
                raise ValueError("Multiple filenames found in libcst.Call node on attempt to apply logfunc parsing rules")
        else:
            unmatched.append(arg)
