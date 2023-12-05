import inspect
from abc import ABC, abstractmethod
from ast import literal_eval
from textwrap import dedent, shorten
from typing import Any, Callable, Optional, Tuple, Type, TypeVar, Union

import libcst as cst
import libcst.matchers as m
from libcst.metadata import BatchableMetadataProvider

__all__ = (
    "ParameterizedClassWrapper",
    "IsNameReferentInstanceOfProvider",
)


class ParameterizedClass(ABC):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    @abstractmethod
    def bind(cls, params: Tuple[Any]):
        ...


T = TypeVar("T", bound=m.BaseMatcherNode)
_G = TypeVar("_G", bound=ParameterizedClass)


class ParameterizedClassWrapper:
    def __init__(self, generic: Type[_G], generic_name: str) -> None:
        self.generic = generic
        self.generic_name = generic_name
        self.subclasses = {}

    def wrap_subclass(self, subcls: Type[_G], subcls_name: str) -> Type[_G]:
        subcls.__name__ = subcls_name
        subcls.__module__ = self.__class__.__module__
        subcls.__doc__ = dedent(
            f"""
            Bound subclass of parameterizable class {self.generic_name}.

            Docstring for {self.generic_name}:

            {self.generic.__doc__}
        """
        ).strip()

        return subcls

    def __getitem__(self, item: Any) -> Type[_G]:
        if not isinstance(item, tuple):
            item = (item,)
        if item not in self.subclasses:

            class _Sub(self.generic):
                pass

            _Sub.bind(item)
            self.subclasses[item] = self.wrap_subclass(
                _Sub, f"{self.generic_name}[{shorten(str(item), 10)}]"
            )
        return self.subclasses[item]

    def __call__(self, *args, **kwargs):
        return self.generic(*args, **kwargs)


class _IsNameReferentInstanceOfProvider(BatchableMetadataProvider, ParameterizedClass):
    """Track which libcst Name nodes reference values matching a given Matcher.

    This is a "parameterized class," in the sense that the metadata provider
    for a given Matcher M has type IsNameReferentInstanceOfProvider[M].
    """

    _matcher: Optional[
        Union[
            m.BaseMatcherNode, Type[m.BaseMatcherNode], Callable[[], m.BaseMatcherNode]
        ]
    ] = None

    @classmethod
    @property
    def matcher(cls):
        if cls._matcher is None:
            raise NotImplementedException(
                f"No default parameter provided for parameterized class {cls}"
            )
        elif isinstance(cls._matcher, m.BaseMatcherNode):
            return cls._matcher
        elif callable(cls._matcher):
            return cls._matcher()
        else:
            raise TypeError(
                f"Parameters bound to class {cls} are not the right type: {cls._matcher}"
            )

    @classmethod
    def bind(cls, params: Tuple[Any]) -> None:
        if len(params) != 1:
            raise TypeError(f"Parameterized class {cls} accepts exactly one parameter")
        if not isinstance(params[0], m.BaseMatcherNode) and not callable(params[0]):
            raise TypeError(
                f"Parameter for class {cls} must be either a callable returning a libcst Matcher or a Matcher instance"
            )
        cls._matcher = params[0]

    def __init__(self) -> None:
        super().__init__()
        self._registry = set()

    def visit_Name(self, node: cst.Name) -> None:
        self.set_metadata(node, node.value in self._registry)

    def visit_Assign(self, node: cst.Assign) -> None:
        if m.matches(
            node,
            m.Assign(targets=[m.AssignTarget(target=m.Name()), m.ZeroOrMore(m.Name())]),
        ):
            if m.matches(node.value, self.matcher):
                self._registry.add(node.targets[0].target.value)


IsNameReferentInstanceOfProvider = ParameterizedClassWrapper(
    _IsNameReferentInstanceOfProvider,
    "IsNameReferentInstanceOfProvider",
)
