from libcst.codemod import CodemodTest
from ..transformers import RemoveEprintDef, ReplaceEprintWithLogger


class TestRemoveEprintDef(CodemodTest):
    TRANSFORM = RemoveEprintDef

    def test_non_eprint_function_def(self) -> None:
        module = """
            def foo(bar):
                print(f"foo {bar}")
        """
        self.assertCodemod(module, module)
