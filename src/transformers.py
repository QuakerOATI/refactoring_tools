import libcst as cst
import libcst.matchers as m
from libcst.helpers import get_full_name_for_node
from .matchers import EprintStatement, TemplateString
from .metadata import IsCaughtException
from typing import List

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


def ExceptionHandlerLoggingStatement(
    function_context: List[str], logger_name="logger"
) -> cst.Call:
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


class FunctionContextMixin(m.MatcherDecoratableTransformer):
    def __init__(self) -> None:
        self.function_context = []

    @m.visit(m.FunctionDef())
    def push_function_onto_context(self, node: cst.FunctionDef) -> None:
        self.function_context.append(get_full_name_for_node(node.name.value))

    @m.leave(m.FunctionDef())
    def pop_function_context(
        self, original: cst.FunctionDef, updated: cst.FunctionDef
    ) -> cst.FunctionDef:
        self.function_context.pop()
        return updated


class ReplaceEprintWithLogger(FunctionContextMixin):
    METADATA_DEPENDENCIES = (IsCaughtException,)

    def __init__(self, logger_name="logger") -> None:
        super().__init__()
        self.excs_in_eprint = []
        self.logger_name = logger_name

    @m.visit(EprintStatement())
    def enter_eprint_context(self, node: cst.Call) -> None:
        self.excs_in_eprint.append(0)

    @m.call_if_inside(EprintStatement())
    @m.visit(m.Arg(m.MatchMetadata(IsCaughtException, True)))
    def set_exc_context(self, node: cst.Arg) -> None:
        self.excs_in_eprint[-1] += 1

    @m.leave(EprintStatement())
    def change_eprint_to_logger(
        self, original: cst.Call, updated: cst.Call
    ) -> cst.Call:
        fmt = updated.args[0].value
        method = updated.args[-1].value.value[1:-1]
        args = updated.args[1:-1]

        if self.excs_in_eprint.pop() > 0:
            return ExceptionHandlerLoggingStatement(
                self.function_context, self.logger_name
            )

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
