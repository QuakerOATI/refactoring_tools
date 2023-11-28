# from libcst.codemod import ContextAwareTransformer, SkipFile, CodemodTest
import libcst as cst
import argparse

from typing import Union, Tuple, TypeVar, List
from ast import literal_eval
from libcst import matchers as m
from libcst import codemod as mod

from .matchers import (
    EprintStatement,
    TemplateString,
)

Statement: TypeVar = Union[cst.SimpleStatementLine, cst.BaseCompoundStatement]


class AddGlobalStatements(mod.VisitorBasedCodemodCommand):
    """Add statements to a module immediately after the imports block.

    This can be done by using either :obj:`libcst.codemod.transform_module` or
    the static method :obj:`AddGLobalStatement.add_global_statement`
    defined on this class, which schedules the addition in a way similar to the
    way :obj:`libcst.codemod.visitors.AddImportsVisitor.add_needed_import`
    works.
    """

    CONTEXT_KEY = "AddGlobalStatement"
    DESCRIPTION = "Add"

    @staticmethod
    def add_global_statement(context: mod.CodemodContext, statement: str):
        """Schedule a global statement to be added in a future invocation.

        Based on the implementation of
        :obj:`libcst.codemod.visitors.AddImportsVisitor.add_needed_import`.
        """
        statements = AddGlobalStatements._get_statements_from_context(context)
        statements.append(statement)
        context.scratch[AddGlobalStatements.CONTEXT_KEY] = statements

    @staticmethod
    def _get_statements_from_context(context: mod.CodemodContext) -> List[str]:
        return context.scratch.get(AddGlobalStatements.CONTEXT_KEY, [])

    def _split_module_with_empty_line(
        self, node: cst.Module, updated_node: cst.Module
    ) -> Tuple[List[Statement], List[Statement]]:
        visitor = mod.visitors.AddImportsVisitor(self.context)
        node.visit(visitor)
        before_add, after_add, after_imports = visitor._split_module(node, updated_node)
        postlude = visitor._insert_empty_line(after_imports)
        return before_add + after_add, postlude

    def _ensure_blank_first_line(self, statement: Statement) -> Statement:
        if not statement.leading_lines:
            return statement.with_changes(leading_lines=(cst.EmptyLine(),))
        elif statement.leading_lines[0].comment is None:
            return statement
        else:
            return statement.with_changes(
                leading_lines=(cst.EmptyLine(), *statement.leading_lines)
            )

    def __init__(self, context: mod.CodemodContext, statements: List[str] = []):
        super().__init__(context)
        self._statements = [*self._get_statements_from_context(context), *statements]

    def leave_Module(self, original: cst.Module, updated: cst.Module) -> cst.Module:
        """Insert statements after all imports and before all others.

        NOTE: The implementation relies on the helper methods
        :obj:`libcst.codemod.visitors.AddImportsVisitor._split_module` and
        :obj:`libcst.codemod.visitors.AddImportsVisitor._insert_empty_line`,
        which are not guaranteed to be stable since they are nonpublic.
        """
        if not self._statements:
            return updated
        prelude, postlude = self._split_module_with_empty_line(original, updated)
        statements = [cst.parse_statement(s) for s in self._statements]
        return updated.with_changes(
            body=(
                *prelude,
                self._ensure_blank_first_line(statements[0]),
                *statements[1:],
                *postlude,
            )
        )


class RemoveEprintDefAndImport(mod.VisitorBasedCodemodCommand):
    """Remove function defs and imports of eprint."""

    DESCRIPTION = "Remove eprint imports and defs."

    @staticmethod
    def add_args(parser: argparse.ArgumentParser) -> None:
        pass

    @m.leave(m.Import(names=[m.AtMostN(n=0)]))
    def remove_empty_import(
        self, original: cst.Import, updated: cst.Import
    ) -> Union[cst.Import, cst.RemovalSentinel]:
        return cst.RemoveFromParent()

    @m.leave(
        m.MatchOr(
            m.ImportAlias(
                name=m.MatchOr(
                    m.Name("eprint"),
                    m.Attribute(attr=m.Name("eprint")),
                )
            ),
            m.ImportAlias(m.Name("eprint")),
        )
    )
    def remove_eprint_import(
        self, original: cst.ImportAlias, updated: cst.ImportAlias
    ) -> Union[cst.ImportAlias, cst.RemovalSentinel]:
        return cst.RemoveFromParent()

    @m.leave(m.FunctionDef(name=m.Name("eprint")))
    def remove_func(
        self, original: cst.FunctionDef, updated: cst.FunctionDef
    ) -> Union[cst.FunctionDef, cst.RemovalSentinel]:
        return cst.RemoveFromParent()


class ReplaceEprintWithLoggerCommand(mod.VisitorBasedCodemodCommand):
    """Replace all eprint calls with logger calls.

    If the eprint call occurs inside an `except` block and at least one of its
    arguments is a caught exception, it will be replaced with a call to
    `logger.exception` with the keyword argument exc_info=True. Otherwise, the
    last argument will be taken as the name of the logger method to use, and
    the first argument to be the template string of message.

    The name of the logger object to use can be passed in the constructor.
    """

    DESCRIPTION: str = "Replace calls to eprint by standard Python logging methods."

    class EprintException(Exception):
        pass

    @staticmethod
    def add_args(parser: argparse.ArgumentParser) -> None:
        pass

    def __init__(self, context: mod.CodemodContext, logger_name="logger") -> None:
        """Constructor for ReplaceEprintWithLogger transformer.

        Args:
            logger_name: name of logger object to use in replacement
        """
        super().__init__(context)
        self.excs_in_eprint = []
        self.logger_name = logger_name
        self.function_context = []
        self.handled_exceptions = set()

    @m.visit(m.FunctionDef())
    def push_function_onto_context(self, node: cst.FunctionDef) -> None:
        self.function_context.append(
            cst.helpers.get_full_name_for_node(node.name.value)
        )

    @m.leave(m.FunctionDef())
    def pop_function_context(
        self, original: cst.FunctionDef, updated: cst.FunctionDef
    ) -> cst.FunctionDef:
        self.function_context.pop()
        return updated

    @m.visit(m.ExceptHandler(name=m.AsName()))
    def push_named_exception(self, node: cst.ExceptHandler) -> None:
        """Track which identifiers refer to caught exceptions."""
        # ExeptHandler.name has type Optional[AsName]
        # AsName.name has type Name
        # Name.value has type str
        exc_name = node.name.name.value
        self.handled_exceptions.add(exc_name)

    @m.leave(m.ExceptHandler(name=m.AsName()))
    def pop_named_exception(
        self, original: cst.ExceptHandler, updated: cst.ExceptHandler
    ) -> cst.ExceptHandler:
        """Pop from self.exception_stack."""
        exc_name = original.name.name.value
        self.handled_exceptions.discard(exc_name)
        return updated

    @m.visit(EprintStatement())
    def enter_eprint_context(self, node: cst.Call) -> None:
        self.excs_in_eprint.append(0)

    @m.call_if_inside(EprintStatement())
    @m.visit(m.Arg(value=m.Name()))
    def set_exc_context(self, node: cst.Arg) -> None:
        if node.value.value in self.handled_exceptions:
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
                self.warn(f"Unrecognized arguments in eprint call: {args}")

        # Now that we've issued warnings about any anomalies, ignore all args
        # other than loglevel and message
        args = []

        # If any args inside the eprint call reference an exception, assume we
        # should replace the call with logger.exception(...)
        if self.excs_in_eprint.pop() > 0:
            return updated.with_changes(
                func=cst.Attribute(
                    val=cst.Name(self.logger_name),
                    attr="exception",
                ),
                args=[
                    cst.Arg(
                        value=cst.SimpleString(f"Error in {self.function_context[0]}")
                    ),
                    cst.Arg(keyword="exc_info", value=cst.Name(value="True")),
                ],
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


class ReplaceStringCommand(mod.VisitorBasedCodemodCommand):
    """Taken from https://libcst.readthedocs.io/en/latest/codemods_tutorial.html."""

    DESCRIPTION: str = "Convert raw strings to imported constants."

    @staticmethod
    def add_args(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--string",
            dest="string",
            metavar="STRING",
            help="String to replace",
            type=str,
            required=True,
        )
        parser.add_argument(
            "--const",
            dest="const",
            metavar="CONST",
            help="Name of constant to import and use to replace STRING",
            type=str,
            required=True,
        )
        parser.add_argument(
            "--module",
            dest="module",
            metavar="MODULE",
            help="Module to import CONST from",
            type=str,
            required=True,
        )

    def __init__(self, context: mod.CodemodContext, string: str, const: str) -> None:
        super().__init__(context)
        self.string = string
        self.const = const

    def leave_SimpleString(
        self, original: cst.SimpleString, updated: cst.SimpleString
    ) -> Union[cst.SimpleString, cst.Name]:
        if literal_eval(updated.value) == self.string:
            mod.AddImportsVisitor.add_needed_import(
                self.context, self.module, self.const
            )
            return cst.Name(self.const)
        return updated
