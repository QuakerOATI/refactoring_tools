from . import *


class TestAddGlobalStatement(CodemodTest):
    TRANSFORM = AddGlobalStatements

    @classmethod
    def setUpClass(cls):
        cls.imports = dedent(
            """
            import json
            import sys, os
            import logging

            from typing import List, Union
            from libcst import codemod as mod
            """
        ).strip()

        cls.function_def = dedent(
            """
            def foo(bar):
                print(bar)
            """
        ).strip()

        cls.logger_declaration = "logger = logging.getLogger(__name__)"
        cls.print_statement = "print('hi there')"

    def test_function_def(self) -> None:
        before = "\n".join([self.imports, "", self.function_def])
        after = "\n".join(
            [self.imports, "", self.logger_declaration, "", self.function_def]
        )
        self.assertCodemod(before, after, [self.logger_declaration])
