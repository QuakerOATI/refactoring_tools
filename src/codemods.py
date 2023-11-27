# from libcst.codemod import ContextAwareTransformer, SkipFile, CodemodTest
import libcst as cst
import argparse

from typing import Union, Tuple, TypeVar, Set, List
from ast import literal_eval
from libcst import matchers as match
from libcst import codemod as mod
from libcst import metadata as meta


Statement: TypeVar = Union[cst.SimpleStatementLine, cst.BaseCompoundStatement]


class AddGlobalStatement(mod.ContextAwareTransformer):
    """Add a statement to a module immediately after the imports block.

    Emits a warning if the statement contains variables not defined or imported
    by the current module.
    """

    def _get_statement_globals(self, statement: str) -> Tuple[cst.Statement, Set[str]]:
        module = cst.parse_module(statement)
        visitor = mod.visitors.GatherGlobalNamesVisitor(
            mod.CodemodContext(wrapper=meta.MetadataWrapper(module))
        )
        module.visit(visitor)
        return cst.parse_statement(statement), visitor.global_names

    def __init__(self, context: mod.CodemodContext, statement_code: str):
        super().__init__(context)
        self._global_names_visitor = mod.visitors.GatherGlobalNamesVisitor(self.context)
        self._imports_visitor = mod.visitors.AddImportsVisitor(self.context)
        context.module.visit(self._global_names_visitor).visit(self._imports_visitor)

        self._statement, self._statement_globals = self._get_statement_globals(
            statement_code
        )

        if not self._statement_globals.issubset(
            self._global_names_visitor.global_names
        ):
            self.warn(
                f"Statement-globals are not defined or imported in module: {self._statement_globals.difference(self._global_names_visitor.global_names)}"
            )

    def leave_Module(self, original: cst.Module, updated: cst.Module) -> cst.Module:
        """Insert statement after all imports and before all others.

        NOTE: The implementation relies on the helper methods
        :obj:`libcst.codemod.visitors.AddImportsVisitor._split_module` and
        :obj:`libcst.codemod.visitors.AddImportsVisitor._insert_empty_line`,
        which are not guaranteed to be stable since they are nonpublic.
        """
        prelude, postlude = self._imports_visitor._split_module(original, updated)
        postlude = self._imports_visitor._insert_empty_line(postlude)
        return updated.with_changes(body=(*prelude, self._statement, *postlude))


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
