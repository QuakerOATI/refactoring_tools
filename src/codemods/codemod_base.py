from .imports import *


class CodemodBase(mod.VisitorBasedCodemodCommand):
    """Automate chaining of codemods via the context.scratch mechanism.

    The :obj:`libcst` codemods :obj:`libcst.codemod.visitors.AddImportsVisitor`
    and :obj:`libcst.codemod.visitors.RemoveImportsVisitor` are applied
    automatically by libcst, without any explicit calls to their
    transform_module methods.  This wrapper class extends that mechanicsm
    to subclasses defined in this package.
    """

    AUTOCHAIN: bool = True

    def transform_module(self, tree: cst.Module) -> cst.Module:
        tree = super().transform_module(tree)
        if self.__class__.AUTOCHAIN:
            if self.__class__.CONTEXT_KEY in self.context.scratch:
                del self.context.scratch[self.__class__.CONTEXT_KEY]
            for transform in self.__class__.__base__.__subclasses__():
                if (
                    transform.CONTEXT_KEY in self.context.scratch
                    and transform.CONTEXT_KEY != self.__class__.CONTEXT_KEY
                ):
                    tree = self._instantiate_and_run(transform, tree)

        return tree
