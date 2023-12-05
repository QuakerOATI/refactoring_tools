import textwrap
from functools import singledispatchmethod, wraps
from inspect import getmembers, isclass, isfunction, signature
from typing import Optional, Type, TypeVar, Union

import makefun

T = TypeVar("T")
_G = TypeVar("_G")


class ParameterizedClassFactory:
    """Create classes parameterized by type-valued parameters.

    This is very similar to typing.Generic, except that "parameters" in this
    case can be arbitrary Python objects, provided they are of the type
    passed in the class-factory's constructor.

    Args:
        generic: an instantiable type to reify
        param_type: parameter type to inject into reified generic
        cls_name: string to set as the __name__ attribute on reified class
        default_param_inst: instance of generic to use as a default if a
            caller attempts to instantiate this class directly.  If an
            Exception instance or subclass is passed for this argument,
            it will be instantiated (if necessary) and raised whenever a
            caller attempts to instantiate the returned parameterized class
            without subscripting by a suitable instance of the generic type
            first.

    Example:

    >>> class _Foo:
    ...     def foo(self, foo: int, bar: str) -> None:
    ...         print(f"{bar}: {foo}")
    >>>
    >>> # This defines Foo as a generic class with a parameter of type str
    >>> Foo = ParameterizedClassFactory(_Foo, str, "Foo")
    >>>
    >>> # This is where the magic happens: the passed parameter is used
    >>> # to dynamically create a subclass of _Foo that automatically
    >>> # substitutes "hello world" for all method arguments annotated with
    >>> # the type str.
    >>> HelloWorldFoo = Foo["hello world"]
    >>> hello_world_instance = HelloWorldFoo()
    >>>
    >>> # As a result, instances of HelloWorldFoo don't have to (and can't)
    >>> # pass string arguments to the .foo method:
    >>> hello_world_instance.foo(3)
    hello world: 3
    """

    def __init__(
        self,
        generic: Type[_G],
        param_type: Type[T],
        cls_name: str,
        default_param_inst: Optional[Union[Exception, T]] = None,
    ) -> None:
        if not isclass(param_type):
            raise TypeError(f"{self.__class__} requires param_type to be a class")
        self._generic = generic
        self._param_type = param_type
        self._cls_name = cls_name
        self._default_inst = default_param_inst
        self._methods = {
            func_name: [
                param_name
                for param_name, param in signature(func).parameters.items()
                if param.annotation is self._param_type
            ]
            for func_name, func in getmembers(self._generic, isfunction)
        }

    def __getitem__(self, item: Type[T]) -> Type[_G]:
        if not isinstance(item, self._param_type):
            raise TypeError(
                f"Parameterized class {self._cls_name} requires a parameter of type {self._param_type}"
            )

        class _Reified(self._generic):
            __name__ = f"{self._cls_name}[{textwrap.shorten(str(item), 10)}]"
            __module__ = self._generic.__module__
            __doc__ = f"""Reification of parameterized class {self._cls_name}.

            Docstring of {self._cls_name}:

            {self._generic.__doc__}
            """

        for name, to_subst in self._methods.items():
            setattr(
                _Reified,
                name,
                makefun.partial(
                    getattr(_Reified, name),
                    **{var: item for var in to_subst},
                ),
            )

        return _Reified

    def __call__(self, *args, **kwargs) -> Type[_G]:
        if isclass(self._default_inst) and issubclass(self._default_inst, Exception):
            raise self._default_inst(
                f"Parameterized class {self._cls_name} can only be instantiated if a parameter instance of type {self._param_type} is explicitly provided"
            )
        elif isinstance(self._default_inst, Exception):
            raise self._default_inst
        else:
            return self[self._default_inst]
