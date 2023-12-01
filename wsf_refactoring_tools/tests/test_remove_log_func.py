from . import *


class TestRemoveLogFuncDefAndImports(CodemodTest):
    TRANSFORM = RemoveLogfuncDefAndImports

    @classmethod
    def setUpClass(cls):
        cls.TRANSFORM.AUTOCHAIN = False
        cls.eprint_def = """
            def eprint(msg, file, level):
                print("{}::{}::{}".format(level, file, msg))
            """

    @classmethod
    def tearDownClass(cls) -> None:
        cls.TRANSFORM.AUTOCHAIN = False

    def setUp(self) -> None:
        # Setting AUTOCHAIN = False allows us to test this
        # transform in isolation
        self.TRANSFORM.AUTOCHAIN = False

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

    def test_logfunc_def(self) -> None:
        before = dedent(
            f"""
            {self.eprint_def}

            eprint("foobar", __file__, "DEBUG")
            """
        ).strip()

        after = dedent(
            f"""
            eprint("foobar", __file__, "DEBUG")
            """
        )

        self.assertCodemod(before, after, expected_warnings=[])

    def test_logfunc_def_with_autochain(self) -> None:
        self.TRANSFORM.AUTOCHAIN = True

        before = dedent(
            f"""
            {self.eprint_def}

            eprint("foobar", __file__, "DEBUG")
            """
        ).strip()

        after = dedent(
            """
            import logging

            logger = logging.getLogger(__name__)


            logger.debug("foobar")
            """
        )

        self.assertCodemod(
            before,
            after,
            expected_warnings=[
                "Unrecognized arguments in logfunc call :: line 3, column 0"
            ],
        )
