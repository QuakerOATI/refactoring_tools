from libcst.codemod import CodemodTest
from ..codemods import (
    AddGlobalStatements,
    ReplaceEprintWithLoggerCommand,
    RemoveEprintDefAndImport,
)
from textwrap import dedent


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


class TestReplaceEprintWithLogger(CodemodTest):
    TRANSFORM = ReplaceEprintWithLoggerCommand

    @classmethod
    def setUpClass(cls):
        cls.preamble = """
            from Baz import baz as qux

            bar = "bar"
            """

        cls.fmt = '"{} is {} is {}"'
        cls.percent_fmt = '"%s is %s is %s"'
        cls.logger_name = "logger"

    def test_INFO(self) -> None:
        before = dedent(
            f"""
            {self.preamble}
            eprint({self.fmt}.format("foo", bar, qux), "INFO")
            """
        ).strip()

        after = dedent(
            f"""
            {self.preamble}
            {self.logger_name}.info({self.percent_fmt}, "foo", bar, qux)
            """
        ).strip()

        self.assertCodemod(before, after, [self.logger_name])
