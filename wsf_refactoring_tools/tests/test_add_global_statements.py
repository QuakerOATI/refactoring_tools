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
            """

        cls.function_def = """
            def foo(bar):
                print(bar)
            """

        cls.logger_declaration = """
            logger = logging.getLogger(__name__)
            """
        cls.print_statement = """
            print('hi there')
            """

    @classmethod
    def tearDownClass(cls) -> None:
        cls.TRANSFORM.AUTOCHAIN = False

    def setUp(self) -> None:
        self.TRANSFORM.AUTOCHAIN = False

    def get_context(self, *statements):
        return CodemodContext(scratch={self.TRANSFORM.CONTEXT_KEY: set(statements)})

    def test_function_def(self) -> None:
        before = f"""
            import json
            import sys, os
            import logging

            from typing import List, Union
            from libcst import codemod as mod

            def foo(bar):
                print(bar)
            """

        after = f"""
            import json
            import sys, os
            import logging

            from typing import List, Union
            from libcst import codemod as mod

            logger = logging.getLogger(__name__)

            def foo(bar):
                print(bar)
            """
        self.assertCodemod(before, after, [dedent(self.logger_declaration).strip()])

    def test_duplicate_statements(self) -> None:
        before = f"""
            import json
            import sys, os
            import logging

            from typing import List, Union
            from libcst import codemod as mod

            def foo(bar):
                print(bar)
            """

        after = f"""
            import json
            import sys, os
            import logging

            from typing import List, Union
            from libcst import codemod as mod

            logger = logging.getLogger(__name__)

            def foo(bar):
                print(bar)
            """

        self.assertCodemod(
            before,
            after,
            context_override=self.get_context(
                dedent(self.logger_declaration).strip(),
                dedent(self.logger_declaration).strip(),
            ),
        )
