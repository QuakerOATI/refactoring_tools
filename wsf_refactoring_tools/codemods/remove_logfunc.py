from .imports import *
from .codemod_base import CodemodBase
from .add_global_statements import AddGlobalStatements
from ..utils.matchers import TemplateString, LogFunctionCall
from ..utils.is_referent_instance_of import IsNameReferentInstanceOfProvider


class RemoveLogfuncDefAndImports(CodemodBase):
    """Remove defs and imports of a specified function.

    The function to be removed is assumed to be a custom logging function.
    Thus, on encountering an import or def of such a function, its name or
    alias is scheduled for replacement by standard logging methods via a
    call to :obj:`ReplaceFuncWithLoggerCommand`.replace_logfunc.
    """

    DESCRIPTION = "Remove imports and defs of specified function."
    CONTEXT_KEY = "RemoveFuncDefAndImports"

    @staticmethod
    def add_args(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--logfunc",
            dest="logfunc",
            metavar="LOGFUNC",
            help="Name of custom log function to replace",
            type=str,
            required=False,
            default="eprint",
        )

    def __init__(self, context: mod.CodemodContext, logfunc: str = "eprint") -> None:
        super().__init__(context)
        self._logfunc = logfunc

    def _filter_import_aliases(
        self, names: List[cst.ImportAlias]
    ) -> List[cst.ImportAlias]:
        keep, discard = [], []
        for node in names:
            if node.evaluated_name.split(".")[-1] != self._logfunc:
                keep.append(node)
            elif node.asname is not None:
                discard.append(node)
                ReplaceFuncWithLoggerCommand.replace_logfunc(self.context, node.asname)
            else:
                discard.append(node)
                ReplaceFuncWithLoggerCommand.replace_logfunc(
                    self.context, node.name.value
                )

        if keep:
            # If last import is removed, make sure there's no trailing comma
            if keep[-1] != names[-1]:
                keep = [
                    *keep[:-1],
                    keep[-1].with_changes(comma=cst.MaybeSentinel.DEFAULT),
                ]
        return keep, discard

    def _remove_references(self, node: Union[cst.ImportAlias, cst.FunctionDef]) -> None:
        if isinstance(node, cst.ImportAlias):
            if node.asname is not None:
                name = node.evaluated_alias
            else:
                name = node.evaluated_name
        elif isinstance(node, cst.FunctionDef):
            name = node.name.value
        ReplaceFuncWithLoggerCommand.replace_logfunc(self.context, node.name.value)

    @m.leave(m.Import())
    @m.leave(m.ImportFrom())
    def leave_import_statement(
        self,
        original: Union[cst.Import, cst.ImportFrom],
        updated: Union[cst.Import, cst.ImportFrom],
    ) -> Union[Union[cst.Import, cst.ImportFrom], cst.RemovalSentinel]:
        """Remove ImportAliases of logfuncs from arbitrary modules.

        The implementation borrows heavily from
        :obj:`libcst.codemod.visitor.RemoveImportsVisitor.leave_Import`.
        """
        if isinstance(original.names, cst.ImportStar):
            return updated
        keep, discard = self._filter_import_aliases(updated.names)
        for node in discard:
            self._remove_references(node)
        if keep:
            return updated.with_changes(names=keep)
        else:
            return cst.RemoveFromParent()

    @m.leave(m.FunctionDef())
    def remove_logfunc(
        self, original: cst.FunctionDef, updated: cst.FunctionDef
    ) -> Union[cst.FunctionDef, cst.RemovalSentinel]:
        if original.name.value == self._logfunc:
            self._remove_references(original)
            return cst.RemoveFromParent()
        else:
            return updated


class ReplaceFuncWithLoggerCommand(CodemodBase):
    """Replace calls to a specified function `func` with logger calls.

    This codemod was created to remove the function "eprint" from the WSF
    codebase.  Accordingly, the following assumptions are made:
        - the log message is the first argument to `func`
        - the loglevel is the last argument to `func`
        - the only other arguments are limited to
            1. a possible named exception, if the call is inside an `except`
                block, and
            2. a possible arguement namd `file` or `File`.

    If the first argument to `func` has the form `msg.format(*args)` for some
    template message msg, then the replacement will be
    `logger.<loglevel>(pmsg, *args)`, where `pmsg` is the same as `msg` but
    with all placeholders {} replaced by old-style %s placeholders.

    If the `func` call occurs inside an `except` block and at least one of its
    arguments is a caught exception, it will be replaced with a call to
    `logger.exception` with the keyword argument exc_info=True. Otherwise, the
    last argument will be taken as the name of the logger method to use, and
    the first argument to be the template string of the message.

    The name of the logger object to use can be passed in the constructor.
    """

    DESCRIPTION: str = (
        "Replace calls to custom logging function with standard Python logging methods."
    )
    CONTEXT_KEY: str = "ReplaceFuncWithLoggerCommand"
    METADATA_DEPENDENCIES = (
        cst.metadata.QualifiedNameProvider,
        cst.metadata.PositionProvider,
        cst.metadata.ScopeProvider,
        IsNameReferentInstanceOfProvider[m.SimpleString()],
    )

    class LogFuncReplaceException(Exception):
        pass

    def warn_at_node(self, node: cst.CSTNode, msg: str) -> None:
        pos = self.get_metadata(cst.metadata.PositionProvider, node).start
        self.warn(f"{msg} :: line {pos.line}, column {pos.column}")

    def raise_at_node(self, node: cst.CSTNode, msg: str) -> None:
        pos = self.get_metadata(cst.metadata.PositionProvider, node).start
        raise self.LogFuncReplaceException(
            f"{msg} :: line {pos.line}, column {pos.column}"
        )

    @staticmethod
    def add_args(parser: argparse.ArgumentParser) -> None:
        pass

    @staticmethod
    def replace_logfunc(context: mod.CodemodContext, name: str) -> None:
        """Schedule a designated custom log function for replacement."""
        context.scratch.setdefault(ReplaceFuncWithLoggerCommand.CONTEXT_KEY, set()).add(
            name
        )

    @staticmethod
    def _get_logger_funcnames_from_context(context: mod.CodemodContext) -> Set[str]:
        return context.scratch.setdefault(ReplaceFuncWithLoggerCommand.CONTEXT_KEY)

    def __init__(
        self,
        context: mod.CodemodContext,
        logger_name="logger",
    ) -> None:
        """Constructor for ReplaceFuncWithLoggerCommand codemod.

        Args:
            log_function_name: name of function to replace with logger calls.
            logger_name: name of logger object to use in replacement
        """
        super().__init__(context)
        self._logfuncs = self._get_logger_funcnames_from_context(context)
        self._excs_in_logfunc_call = []
        self._logger_name = logger_name
        self._function_context = []
        self._handled_exceptions = set()

    @m.visit(m.Module())
    def check_global_scope_for_logger(self, node: cst.Module) -> None:
        """Define logger at module scope, provided it's not already defined."""
        global_scope = self.get_metadata(cst.metadata.ScopeProvider, node)
        if self._logger_name in global_scope:
            raise self.LogFuncReplaceException(
                f"Module scope already contains the name {self._logger_name}"
            )
        else:
            AddGlobalStatements.add_global_statement(
                self.context,
                f"{self._logger_name} = logging.getLogger(__name__)",
            )

    @m.visit(m.FunctionDef())
    def push_function_onto_context(self, node: cst.FunctionDef) -> None:
        self._function_context.append(node)

    @m.leave(m.FunctionDef())
    def pop_function_context(
        self, original: cst.FunctionDef, updated: cst.FunctionDef
    ) -> cst.FunctionDef:
        self._function_context.pop()
        return updated

    @m.visit(m.ExceptHandler(name=m.AsName()))
    def push_named_exception(self, node: cst.ExceptHandler) -> None:
        """Track which identifiers refer to caught exceptions."""
        # ExeptHandler.name has type Optional[AsName]
        # AsName.name has type Name
        # Name.value has type str
        exc_name = node.name.name.value
        self._handled_exceptions.add(exc_name)

    @m.leave(m.ExceptHandler(name=m.AsName()))
    def pop_named_exception(
        self, original: cst.ExceptHandler, updated: cst.ExceptHandler
    ) -> cst.ExceptHandler:
        """Pop from self.exception_stack."""
        exc_name = original.name.name.value
        self._handled_exceptions.discard(exc_name)
        return updated

    @m.visit(LogFunctionCall())
    def enter_logfunc_context(self, node: cst.Call) -> None:
        if node.func.value in self._logfuncs:
            self._excs_in_logfunc_call.append(0)
            mod.visitors.AddImportsVisitor.add_needed_import(self.context, "logging")

            # If there are any additional args other than file and/or an
            # exception, raise warning
            # The file args can be safely ignored, since we can include that
            # information by configuring the root logger's formatter
            for a in node.args[1:-1]:
                if not m.matches(
                    a, m.Arg(value=m.Name("file") | m.Name("File"))
                ) and not m.matches(
                    a,
                    m.Arg(
                        value=m.Name(
                            value=m.MatchIfTrue(
                                lambda value: value in self._handled_exceptions
                            )
                        )
                    ),
                ):
                    self.warn_at_node(node, "Unrecognized arguments in logfunc call")
                    break

    @m.call_if_inside(LogFunctionCall())
    @m.visit(m.Arg(value=m.Name()))
    def set_exc_context(self, node: cst.Arg) -> None:
        if node.value.value in self._handled_exceptions:
            if self._excs_in_logfunc_call:
                self._excs_in_logfunc_call[-1] += 1

    @m.leave(LogFunctionCall())
    def change_logfunc_to_logger(
        self, original: cst.Call, updated: cst.Call
    ) -> cst.Call:
        """Remove and replace eprint :obj:`libcst.Call` nodes."""
        if original.func.value not in self._logfuncs:
            return updated
        fmt = original.args[0].value
        method = literal_eval(original.args[-1].value.value)

        # We've already issued warnings about any anomalies in
        # enter_logfunc_context, so here we just ignore all args
        # other than loglevel and message
        args = []

        # If any args inside the eprint call reference an exception, assume we
        # should replace the call with logger.exception(...)
        if self._excs_in_logfunc_call.pop() > 0:
            if self._function_context:
                try:
                    # The QualifiedNameProvider returns a set() of *possible*
                    # qualified names, of which we only need one
                    exc_scope = (
                        self.get_metadata(
                            cst.metadata.QualifiedNameProvider,
                            self._function_context[-1],
                        )
                        .pop()
                        .name
                    )
                except KeyError:
                    # pop from an empty set
                    self.warn_at_node(
                        original,
                        "Unable to find qualified name for function context of exception (QualifiedNameProvider returned empty set)",
                    )
                    exc_scope = "UNKNOWN"
            else:
                exc_scope = "Module"
            msg = f"Error in function: {exc_scope}"
            return updated.with_changes(
                func=cst.Attribute(
                    value=cst.Name(self._logger_name),
                    attr=cst.Name("exception"),
                ),
                args=[
                    cst.Arg(value=cst.SimpleString(f'"{msg}"')),
                    cst.Arg(
                        keyword=cst.Name("exc_info"),
                        value=cst.Name(value="True"),
                        equal=cst.AssignEqual(
                            whitespace_before=cst.SimpleWhitespace(""),
                            whitespace_after=cst.SimpleWhitespace(""),
                        ),
                    ),
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
            # ...let's just double-check though :)
            try:
                _ = fmt % tuple("string" for _ in args)
            except TypeError:
                self.raise_at_node(
                    original,
                    "Failed to convert str.format() call to %-style format string",
                )
        else:
            self.raise_at_node(
                original, "Unknown format for first logger function argument"
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
