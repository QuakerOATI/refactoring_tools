from .imports import *


class AddImportsCodemodCommand(mod.VisitorBasedCodemodCommand):
    @staticmethod
    def add_args(parser: argparse.ArgumentParser):
        parser.add_argument(
            "--module",
            "-m",
            dest="modules",
            metavar="MODULE",
            help="ensure module is imported",
            action="append",
            default=[],
            required=False,
        )

    def __init__(self, context: mod.CodemodCommand, imports: List[str]) -> None:
        super().__init__(context)
        for module in modules:
            mod.visitors.AddImportsVisitor.add_needed_import(self.context, module)
