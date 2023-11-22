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


class LastArgument(
    cst.metadata.BatchableMetadataProvider[Optional[cst.BaseExpression]]
):
    """Marks function calls with the value of their last argument."""

    def visit_Call(self, node: cst.Call) -> None:
        if node.args:
            self.set_metadata(node, node.args[-1].value)
        else:
            self.set_metadata(node, None)


class IsFirstArgument(cst.metadata.BatchableMetadataProvider[bool]):
    """Marks the first argument of each function call."""

    def visit_Call(self, node: cst.Call) -> None:
        if node.args:
            self.set_metadata(node.args[0], True)


class IsLogLevelLiteral(cst.metadata.BatchableMetadataProvider[bool]):
    """Marks the string literals corresponding to named logging levels."""

    def visit_SimpleString(self, node: cst.SimpleString) -> None:
        self.set_metadata(
            node,
            node.value in ["DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL"],
        )


LOGLEVELS = ["DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL", "FATAL"]


def LogLevelLiteral():
    return m.SimpleString(value=m.matches(lambda value: value in LOGLEVELS))


def TemplateString():
    return m.Call(func=m.Attribute(value=m.SimpleString, attr=m.Name(value="format")))


def EprintStatement():
    return m.Call(
        func=m.Name(value="eprint"),
        args=m.MatchIfTrue(
            lambda args: args and m.matches(args[-1], LogLevelLiteral())
        ),
    )


class ReplaceEprintWithLogger(m.MatcherDecoratableTransformer):
    @m.leave(EprintStatement())
    def change_eprint_to_logger(self, original: cst.Call, updated: cst.Call):
        args = updated.args[:-1]
        fmt = args[0]
        if m.matches(TemplateString(), fmt):
            spec = ...
        if m.matches(last_arg := updated.args[-1], m.Arg(value=m.SimpleString())):
            if (loglevel := last_arg.value) in LOGLEVELS:
                return updated.with_changes(
                    func=cst.Attribute(
                        value=cst.Name(value="logger"),
                        attr=cst.Name(value=loglevel.lower()),
                    ),
                    args=[
                        cst.Arg(value=cst.SimpleString(value=printf_template)),
                        *printf_args,
                    ],
                )

    @m.call_if_inside(EprintStatement())
    @m.visit(TemplateString())
    def unroll_formatted_string(self, node: cst.Call) -> None:
        fmt = cst.Arg(node.func.value)
        return cst.List([fmt, *node.func.args])


class IsFormatString(cst.metadata.BatchableMetadataProvider[bool]):
    """Marks calls to .format(...) on strings literal."""

    def visit_SimpleString(self, node: cst.SimpleString) -> None:
        ...


class ConvertBraceFormatToPercent(m.MatcherDecoratableTransformer):
    def update_function(self, original: cst.Call, updated: cst.Call):
        ...
