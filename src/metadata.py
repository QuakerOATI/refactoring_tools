import libcst.matchers as m
import libcst.metadata as meta
import libcst as cst


class IsCaughtException(meta.BatchableMetadataProvider[bool]):
    """Metadata provider that marks identifiers of caught exceptions."""

    def __init__(self) -> None:
        self.exception_stack = []
        self.handled_exceptions = {}

    @m.call_if_inside(m.ExceptHandler())
    @m.visit(m.Name())
    def mark_caught_exceptions(self, node: cst.Name) -> None:
        """Set metadata to True on Name nodes that refer to caught exceptions."""
        if node.value in self.handled_exceptions:
            self.set_metadata(node, True)

    @m.visit(m.ExceptHandler(name=m.AsName()))
    def push_named_exception(self, node: cst.ExceptHandler) -> None:
        """Track which identifiers refer to caught exceptions."""
        # ExeptHandler.name has type Optional[AsName]
        # AsName.name has type Name
        # Name.value has type str
        exc_name = node.name.name.value
        exc_type = node.type
        self.handled_exceptions[exc_name] = exc_type

    @m.visit(m.ExceptHandler())
    def enter_except_handler(self, node: cst.ExceptHandler) -> None:
        """Track how many `except` blocks we're currently in."""
        self.exception_stack.append((node.name, node.type))

    @m.leave(m.ExceptHandler())
    def leave_except_handler(
        self, original: cst.ExceptHandler, updated: cst.ExceptHandler
    ) -> cst.ExceptHandler:
        """Pop from self.exception_stack.

        If the current except block assigned the caught exception to a
        variable, then remove its name from self.handled_exceptions.
        """
        exc_name, _ = self.handled_exceptions.pop()
        if exc_name is not None:
            del self.handled_exceptions[exc_name.name.value]
