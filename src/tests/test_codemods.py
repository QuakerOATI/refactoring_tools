import libcst as cst
from unittest.mock import Mock
from libcst.codemod import CodemodTest, CodemodContext
from libcst.metadata import MetadataWrapper
from ..codemods import (
    AddGlobalStatements,
    ReplaceFuncWithLoggerCommand,
    RemoveLogfuncDefAndImports,
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


class TestReplaceFuncWithLoggerCommand(CodemodTest):
    TRANSFORM = ReplaceFuncWithLoggerCommand

    @classmethod
    def setUpClass(cls):
        cls.preamble = """
            from Baz import baz as qux

            bar = "bar"
            """

        cls.fmt = '"{} is {} is {}"'
        cls.error_fmt = '"Exception: {}"'
        cls.percent_fmt = '"%s is %s is %s"'
        cls.logger_name = "logger"
        cls.context = CodemodContext(
            scratch={cls.TRANSFORM.CONTEXT_KEY: {"eprint"}},
        )

    def get_scopes(self, before_code: str):
        wrapper = cst.metadata.MetadataWrapper(
            cst.parse_module(dedent(before_code).strip())
        )
        return wrapper.module, wrapper.resolve(cst.metadata.ScopeProvider)

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

        self.assertCodemod(
            before, after, self.logger_name, context_override=self.context
        )

    def test_exception(self) -> None:
        before = dedent(
            f"""
            {self.preamble}
            try:
                raise ValueError("oops")
            except ValueError as e:
                eprint({self.error_fmt}.format(e), __file__, "INFO")
            """
        ).strip()

        after = dedent(
            f"""
            {self.preamble}
            try:
                raise ValueError("oops")
            except ValueError as e:
                logger.exception("Error in function: UNKNOWN", exc_info=True)
            """
        )

        self.assertCodemod(
            before, after, self.logger_name, context_override=self.context
        )

    def test_exception_with_function_scope(self) -> None:
        before = dedent(
            f"""
            {self.preamble}

            def foo(bar: int) -> int:
                try:
                    return 1/bar
                except ZeroDivisionError as e:
                    eprint({self.error_fmt}.format(e), __file__, "INFO")
            """
        ).strip()

        after = dedent(
            f"""
            {self.preamble}

            def foo(bar: int) -> int:
                try:
                    return 1/bar
                except ZeroDivisionError as e:
                    logger.exception("Error in function: foo", exc_info=True)
            """
        )

        self.assertCodemod(
            before, after, self.logger_name, context_override=self.context
        )


class TestRemoveLogFuncDefAndImports(CodemodTest):
    TRANSFORM = RemoveLogfuncDefAndImports

    @classmethod
    def setUpClass(cls):
        cls.eprint_def = """
            def eprint(msg, file, level):
                print("{}::{}::{}".format(level, file, msg))
            """

    def test_simple_import(self) -> None:
        before = dedent(
            """
            import funcs.eprint as printe

            printe("hi there")
            """
        ).strip()

        after = dedent(
            """

            printe("hi there")
            """
        ).strip()

        self.assertCodemod(before, after)

    def test_import_group(self) -> None:
        before = dedent(
            """
            import fprint, gprint, eprint
            eprint("floop")
            """
        ).strip()

        after = dedent(
            """
            import fprint, gprint
            eprint("floop")
            """
        ).strip()

        self.assertCodemod(before, after)

    def test_importFrom_group(self) -> None:
        before = dedent(
            """
            from module import fprint, gprint, eprint
            eprint("floop")
            """
        ).strip()

        after = dedent(
            """
            from module import fprint, gprint
            eprint("floop")
            """
        ).strip()

        self.assertCodemod(before, after)
