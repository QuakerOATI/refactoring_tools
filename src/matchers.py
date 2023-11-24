import libcst.matchers as m


LOGLEVELS = ["DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL", "FATAL"]


def LogLevelLiteral():
    """Matcher factory for use with libcst.matchers functions and decorators."""
    # Note that SimpleString.value includes the quotes, so we have to check value[1:-1]
    return m.SimpleString(value=m.MatchIfTrue(lambda value: value[1:-1] in LOGLEVELS))


def TemplateString():
    """Matcher factory for use with libcst.matchers functions and decorators."""
    return m.Call(func=m.Attribute(value=m.SimpleString(), attr=m.Name(value="format")))


def EprintStatement():
    """Matcher factory for use with libcst.matchers functions and decorators."""
    return m.Call(
        func=m.Name(value="eprint"),
        args=m.MatchIfTrue(
            lambda args: args and m.matches(args[-1].value, LogLevelLiteral())
        ),
    )
