import libcst as cst
import libcst.matchers as m
from libcst.metadata import BatchableMetadataProvider
from .parameterized_class_factory import ParameterizedClassFactory


class _IsNameReferentInstanceOfProvider(BatchableMetadataProvider):
    """Track which libcst Name nodes reference values matching a given Matcher.

    This is a "parameterized class," in the sense that the metadata provider
    for a given Matcher M has type IsNameReferentInstanceOfProvider[M].
    """

    def __init__(self) -> None:
        super().__init__()
        self._registry = set()

        @m.visit(m.Name())
        def mark_name(self, node: cst.Name) -> None:
            self.set_metadata(node, node.value in self._registry)

        @m.visit(m.Assign(targets=[m.AssignTarget(target=m.Name())]))
        def register_assigned(
            self, node: cst.Assign, matcher: m.BaseMatcherNode
        ) -> None:
            if m.matches(node.value, matcher):
                self._registry.add(node.targets[0].value)


IsNameReferentInstanceOfProvider = ParameterizedClassFactory(
    _IsNameReferentInstanceOfProvider,
    m.BaseMatcherNode,
    "IsNameReferentInstanceOfProvider",
)
