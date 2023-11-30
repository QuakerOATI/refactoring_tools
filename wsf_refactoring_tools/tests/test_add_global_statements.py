from . import *


class TestAddGlobalStatement(CodemodTest):
    TRANSFORM = AddGlobalStatements

    @classmethod
    def setUpClass(cls):
        cls.TRANSFORM.AUTOCHAIN = False
        cls.imports = """
            import json
            import sys, os
            import logging

            from typing import List, Union
            from libcst import codemod as mod
            """.removeprefix(
            "\n"
        ).removesuffix(
            "\n"
        )

        cls.function_def = """
            def foo(bar):
                print(bar)
            """.removeprefix(
            "\n"
        ).removesuffix(
            "\n"
        )

        cls.logger_declaration = "logger = logging.getLogger(__name__)"
        cls.print_statement = "print('hi there')"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.TRANSFORM.AUTOCHAIN = False

    def setUp(self) -> None:
        self.TRANSFORM.AUTOCHAIN = False

    def get_context(self, *statements):
        return CodemodContext(scratch={self.TRANSFORM.CONTEXT_KEY: set(statements)})

    def test_function_def(self) -> None:
        before = f"""
            {self.imports}

            {self.function_def}
            """

        after = f"""
            {self.imports}

            {self.logger_declaration}

            {self.function_def}
            """
        self.assertCodemod(before, after, [self.logger_declaration])

    def test_duplicate_statements(self) -> None:
        before = f"""
            {self.imports}

            {self.function_def}
            """

        after = f"""
            {self.imports}

            {self.logger_declaration}
            {self.function_def}
            """

        self.assertCodemod(
            before,
            after,
            context_override=self.get_context(
                self.logger_declaration, self.logger_declaration
            ),
        )
