import libcst as cst
import libcst.codemod as mod
import libcst.matchers as m
from typing import Optional

"""
1. Rename eprint --> logger method
2. Reconstruct arguments to eprint/logger method
3. When in a catch block, use the logger.exception method
    - only when eprint statement has an argument equal to the target of an "Exception as" assignment

Needed components:
    * "name is exception" provider
        * matcher for except blocks
    * matcher for first and last args to function call
    * matcher for string.format() expressions
    * transformer for format --> printf conversion
    * IsLoggerStatement matcher

Existing components:
    * cst.Raise
        - includes attribute for optional "from" clase
    * cst.Try
        - cannot contain TryStar blocks
        - Try.handlers
    * cst.ExceptHandler
        - handler.body
        - handler.type: Tuple[...] or None
        - name --> name of caught exception

Notes:
    * can match on number of arguments to Call
    * declare metadata providers with METADATA_DEPENDENCIES class attribute
        * metadata is then accessed via self.get_metadata(provider_type, node)
    * providers should extend BatchableMetadataProvider
    * ParentNodeProvider can be used for backtracking

Ideas:
    * cst.metadata.QualifiedNameProvider/FullyQualifiedNameProvider:
        - use to automate import restructuring
    * match.MatchIfTrue:
        - match name against predefined list

"""


LOGLEVELS = ["DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL", "FATAL"]


def LogLevelLiteral():
    """Factory for use with libcst.matchers functions and decorators"""
    # Note that SimpleString.value includes the quotes, so we have to check value[1:-1]
    return m.SimpleString(value=m.MatchIfTrue(lambda value: value[1:-1] in LOGLEVELS))


def TemplateString():
    """Factory for use with libcst.matchers functions and decorators"""
    return m.Call(func=m.Attribute(value=m.SimpleString(), attr=m.Name(value="format")))


def EprintStatement():
    """Factory for use with libcst.matchers functions and decorators"""
    return m.Call(
        func=m.Name(value="eprint"),
        args=m.MatchIfTrue(
            lambda args: args and m.matches(args[-1].value, LogLevelLiteral())
        ),
    )


class ReplaceEprintWithLogger(m.MatcherDecoratableTransformer):
    @m.leave(EprintStatement())
    def change_eprint_to_logger(self, original: cst.Call, updated: cst.Call):
        fmt = updated.args[0].value
        method = updated.args[-1].value.value[1:-1]
        args = updated.args[1:-1]
        if m.matches(fmt, m.SimpleString()):
            fmt = fmt.value
        elif m.matches(fmt, TemplateString()):
            args = fmt.args + args
            fmt = fmt.func.value.value.replace("{}", "%s")
        else:
            raise ValueError(f"Unknown format for first eprint argument: {fmt}")
        return updated.with_changes(
            func=cst.Attribute(
                value=cst.Name(value="logger"),
                attr=cst.Name(method.lower()),
            ),
            args=[
                cst.Arg(value=cst.SimpleString(value=fmt)),
                *args,
            ],
        )
