import libcst as cst
import libcst.matchers as m
from libcst.helpers import get_full_name_for_node
from .matchers import EprintStatement, TemplateString
from .metadata import IsCaughtException
from typing import List, Union

"""Transformers for refactoring the webSmartForecast codebase."""


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


class FunctionContextMixin(m.MatcherDecoratableTransformer):
    """Mixin for a transformer that maintains nested-function context."""

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


class RemoveEprintDef(m.MatcherDecoratableVisitor):
    """Remove function defs of eprint."""

    @m.leave(m.FunctionDef(name=m.Name("eprint")))
    def remove_func(
        self, original: cst.FunctionDef, updated: cst.FunctionDef
    ) -> Union[cst.FunctionDef, cst.RemovalSentinel]:
        return cst.RemoveFromParent()


class ReplaceEprintWithLogger(FunctionContextMixin):
    """Replace all eprint calls with logger calls.

    If the eprint call occurs inside an `except` block and at least one of its
    arguments is a caught exception, it will be replaced with a call to
    `logger.exception` with the keyword argument exc_info=True. Otherwise, the
    last argument will be taken as the name of the logger method to use, and
    the first argument to be the template string of message.

    The name of the logger object to use can be passed in the constructor.
    """

    METADATA_DEPENDENCIES = (IsCaughtException,)

    class EprintWarning(Warning):
        pass

    class EprintException(Exception):
        pass

    def __init__(self, logger_name="logger") -> None:
        """Constructor for ReplaceEprintWithLogger transformer.

        Args:
            logger_name: name of logger object to use in replacement
        """
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

        if args:
            # If there are any additional args other than file, raise warning
            # The file args can be safely ignored, since we can include that
            # information by coniguring the root logger's formatter
            if any(
                map(
                    m.matches(
                        m.Arg(value=m.DoesNotMatch(m.Name("file") | m.Name("File"))),
                        args,
                    )
                )
            ):
                raise self.EprintWarning(
                    f"Unrecognized arguments in eprint call: {args}"
                )

        # Now that we've issued warnings about any anomalies, ignore all args
        # other than loglevel and message
        args = []

        # If any args inside the eprint call reference an exception, assume we
        # should replace the call with logger.exception(...)
        if self.excs_in_eprint.pop() > 0:
            return ExceptionHandlerLoggingStatement(
                self.function_context, self.logger_name
            )

        # First arg should be either a format string or a simple string
        if m.matches(fmt, m.SimpleString()):
            fmt = fmt.value
        elif m.matches(fmt, TemplateString()):
            # The args we want are in the call to .format()
            args = fmt.args
            # Simpleminded, but Good Enough for this use case
            fmt = fmt.func.value.value.replace("{}", "%s")
        else:
            raise self.EprintException(
                f"Unknown format for first eprint argument: {fmt}"
            )

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
