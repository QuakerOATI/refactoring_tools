from .imports import *
from .codemod_base import CodemodBase

Statement: TypeVar = Union[cst.SimpleStatementLine, cst.BaseCompoundStatement]


class AddGlobalStatements(CodemodBase):
    """Add statements to a module immediately after the imports block.

    This can be done by using either :obj:`libcst.codemod.transform_module` or
    the static method :obj:`AddGLobalStatement.add_global_statement`
    defined on this class, which schedules the addition in a way similar to the
    way :obj:`libcst.codemod.visitors.AddImportsVisitor.add_needed_import`
    works.
    """

    CONTEXT_KEY = "AddGlobalStatements"
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
