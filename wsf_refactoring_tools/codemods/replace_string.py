from .imports import *
from .codemod_base import CodemodBase


class ReplaceStringCommand(CodemodBase):
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
