from ast import literal_eval
from dataclasses import dataclass
from typing import Any, List, Literal, Optional, Tuple, Union
from .imports import *
from ..utils.matchers import LogFunctionCall, TemplateString
from .add_global_statements import AddGlobalStatements
from .codemod_base import CodemodBase

LOGLEVELS = ["DEBUG", "INFO", "WARNING", "WARN", "ERROR", "CRITICAL", "FATAL"]


@dataclass
class CSTString:
    name: Optional[cst.Name] = None
    literal: Optional[cst.SimpleString] = None
    format_args: Optional[Tuple[cst.Arg]] = tuple()


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
        return context.scratch.setdefault(ReplaceFuncWithLoggerCommand.CONTEXT_KEY, set())

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
        self._string_varnames = {}
        self._postprocess = set()

    def ensure_assigned_format_is_percent(self, node: cst.Name) -> None:
        if node.value in self._string_varnames:
            map = self._string_varnames[node.value]
            # map is None if no postprocessing is needed
            if map is None:
                return
            scope = self.get_metadata(meta.ScopeProvider, node)
            while scope not in map:
                parent = scope.parent
                if scope is parent:
                    self.raise_at_node(
                        node, "Could not find scope of string variable definition"
                    )
            self._postprocess.add(map[scope])

    def get_string_components(
        self, node: Union[cst.Name, cst.Call, cst.SimpleString]
    ) -> Optional[CSTString]:
        """Check if the passed node is a str, str.format, or string ref."""
        if m.matches(node, m.SimpleString()):
            return CSTString(literal=literal_eval(node.value))
        elif m.matches(node, m.Call(func=m.Attribute(attr=m.Name("format")))):
            ret = CSTString(format_args=node.args)
            if m.matches(node.func.value, m.SimpleString()):
                ret.literal = literal_eval(node.func.value.value)
            elif (
                m.matches(node.func.value, m.Name())
                and node.func.value.value in self._string_varnames
            ):
                ret.name = node.func.value
            return ret
        elif m.matches(node, m.Name()) and node.value in self._string_varnames:
            return CSTString(name=node)
        return None

    def get_logfunc_arguments(self, node: cst.Call) -> Tuple[str, CSTString, Exception]:
        """Get loglevel, message, and possible Exception instance from logfunc call."""
        loglevel, msg = None, None
        unrecognized = 0
        for arg in node.args:
            if (comps := self.get_string_components(arg.value)) is not None:
                # arg is a string
                if comps.literal in LOGLEVELS:
                    if loglevel is not None:
                        self.raise_at_node("Multiple loglevels in logfunc call")
                    loglevel = comps.literal
                elif comps.name is not None and comps.name.value.lower() == "file":
                    self.warn_at_node(node, "File argument in logfunc call")
                elif msg is None:
                    msg = comps
                else:
                    unrecognized += 1
            elif (
                m.matches(arg.value, m.Name())
                and arg.value.value in self._handled_exceptions
            ):
                # handled below
                pass
            else:
                unrecognized += 1
        if unrecognized > 0:
            self.warn_at_node(
                node, f"{unrecognized} unrecognized argument(s) found in logfunc call"
            )
        if msg is None or loglevel is None:
            self.raise_at_node(node, "Malformed logfunc call")
        return loglevel, msg

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

    @m.leave(m.Module())
    def postprocess_assignment_nodes(
        self, module: cst.Module, updated: cst.Module
    ) -> cst.Module:
        def convert_format(node: cst.Assign) -> cst.Assign:
            bracket_fmt = literal_eval(node.value.value)
            percent_fmt = repr(bracket_fmt.replace("{}", "%s"))
            return node.with_changes(value=node.value.with_changes(value=percent_fmt))

        if self._postprocess:
            for node in self._postprocess:
                updated = updated.deep_replace(node, convert_format(node))
        return updated

    @m.visit(m.FunctionDef())
    def push_function_onto_context(self, node: cst.FunctionDef) -> None:
        self._function_context.append(node)

    @m.leave(
        m.Assign(
            targets=[m.AssignTarget(target=m.Name()), m.ZeroOrMore(m.Name())],
            value=m.SimpleString(),
        )
    )
    def record_string_assignment(
        self, node: cst.Assign, updated: cst.Assign
    ) -> cst.Assign:
        scope = self.get_metadata(meta.ScopeProvider, node.targets[0].target)
        self._string_varnames.setdefault(node.targets[0].target.value, {})[
            scope
        ] = updated
        return updated

    @m.leave(
        m.Assign(
            targets=[m.AssignTarget(target=m.Name()), m.ZeroOrMore(m.Name())],
            value=m.Call(func=m.Attribute(attr=m.Name(value="format"))),
        )
    )
    def record_template_string_assignment(
        self, node: cst.Assign, updated: cst.Assign
    ) -> cst.Assign:
        caller = node.value.func.value
        if m.matches(caller, m.SimpleString()) or m.matches(
            caller,
            m.Name(value=m.MatchIfTrue(lambda value: value in self._string_varnames)),
        ):
            scope = self.get_metadata(meta.ScopeProvider, node.targets[0].target)
            # the string variable name has to be in self._string_varnames, but we associate it with None
            # to ensure that no format correction (postprocessing) occurs
            self._string_varnames.setdefault(node.targets[0].target.value, {})[
                scope
            ] = None
        return updated

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

    @m.call_if_inside(m.Call(func=m.Name()))
    @m.visit(m.Arg(value=m.Name()))
    def set_exc_context(self, node: cst.Arg) -> None:
        if node.value.value in self._handled_exceptions:
            if self._excs_in_logfunc_call:
                self._excs_in_logfunc_call[-1] += 1

    @m.visit(m.Call(func=m.Name()))
    def enter_logfunc_context(self, node: cst.Call) -> None:
        if node.func.value in self._logfuncs:
            self._excs_in_logfunc_call.append(0)
            mod.visitors.AddImportsVisitor.add_needed_import(self.context, "logging")

    @m.leave(m.Call(func=m.Name()))
    def change_logfunc_to_logger(
        self, original: cst.Call, updated: cst.Call
    ) -> cst.Call:
        """Remove and replace eprint :obj:`libcst.Call` nodes."""
        if original.func.value not in self._logfuncs:
            return updated
        loglevel, msg = self.get_logfunc_arguments(original)

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

        if msg.format_args:
            if msg.name is not None:
                self.ensure_assigned_format_is_percent(msg.name)
            else:
                # Simpleminded, but Good Enough for this use case
                msg.literal = msg.literal.replace("{}", "%s")
                try:
                    _ = msg.literal % tuple("string" for _ in msg.format_args)
                except TypeError:
                    self.raise_at_node(
                        original,
                        "Failed to convert str.format() call to %-style format string",
                    )
        fmt = (
            msg.name
            if msg.name is not None
            else cst.SimpleString(value=repr(msg.literal))
        )

        return updated.with_changes(
            func=cst.Attribute(
                value=cst.Name(value="logger"),
                attr=cst.Name(loglevel.lower()),
            ),
            args=[cst.Arg(value=fmt), *msg.format_args],
        )
