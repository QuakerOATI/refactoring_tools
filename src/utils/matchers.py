import libcst.matchers as m
import libcst as cst
from ast import literal_eval
from typing import List


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
        ],
    )


def ExceptionHandlerLoggingStatement(
    function_context: List[str], logger_name="logger"
) -> cst.Call:
    """Factory for a libcst node representing a logger.exception call."""

    return cst.Call(
        func=cst.Attribute(
            val=cst.Name(logger_name),
            attr="exception",
        ),
        args=[
            cst.Arg(value=cst.SimpleString(f"Error in {function_context[0]}")),
            cst.Arg(keyword="exc_info", value=cst.Name(value="True")),
        ],
    )