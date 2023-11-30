from . import *


class TestReplaceFuncWithLoggerCommand(CodemodTest):
    TRANSFORM = ReplaceFuncWithLoggerCommand

    @classmethod
    def setUpClass(cls):
        cls.TRANSFORM.AUTOCHAIN = False
        cls.preamble = """from Baz import baz as qux"""

        cls.fmt = '"{} is {} is {}"'
        cls.error_fmt = '"Exception: {}"'
        cls.percent_fmt = '"%s is %s is %s"'
        cls.logger_name = "logger"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.TRANSFORM.AUTOCHAIN = False

    def setUp(self) -> None:
        # The context has to be refreshed for every test method, which is
        # why this isn't in setUpClass
        self.context = CodemodContext(
            scratch={self.TRANSFORM.CONTEXT_KEY: {"eprint"}},
        )
        self.TRANSFORM.AUTOCHAIN = False

    def tearDown(self) -> None:
        self.TRANSFORM.AUTOCHAIN = False

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
            import logging

            {self.logger_name}.info({self.percent_fmt}, "foo", bar, qux)
            """
        ).strip()

        self.assertCodemod(
            before, after, self.logger_name, context_override=self.context
        )

    def test_malformed_logfunc_call(self) -> None:
        before = dedent(
            f"""
            eprint({self.fmt}.format("foo", bar, qux), x, __file__, "INFO")
            """
        ).strip()

        after = dedent(
            f"""
            import logging

            {self.logger_name}.info({self.percent_fmt}, "foo", bar, qux)
            """
        ).strip()

        self.assertCodemod(
            before,
            after,
            self.logger_name,
            context_override=self.context,
            expected_warnings=[
                f"Unrecognized arguments in logfunc call: line 1, column 0",
            ],
        )

    def test_exception_at_module_scope(self) -> None:
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
            import logging

            try:
                raise ValueError("oops")
            except ValueError as e:
                logger.exception("Error in function: Module", exc_info=True)
            """
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
            import logging

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

    def test_exception_function_scope_nested_exceptions(self) -> None:
        before = dedent(
            f"""
            {self.preamble}
            def foo(bar):
                try:
                    print("Is this safe?")
                    try:
                        raise ValueError("oops")
                    except ValueError as e:
                        eprint({self.error_fmt}.format(e), __file__, "INFO")
                except Exception:
                    eprint("outer exception", "ERROR")
            """
        ).strip()

        after = dedent(
            f"""
            {self.preamble}
            import logging

            def foo(bar):
                try:
                    print("Is this safe?")
                    try:
                        raise ValueError("oops")
                    except ValueError as e:
                        logger.exception("Error in function: foo", exc_info=True)
                except Exception:
                    logger.error("outer exception")
            """
        )
        self.assertCodemod(
            before, after, self.logger_name, context_override=self.context
        )
