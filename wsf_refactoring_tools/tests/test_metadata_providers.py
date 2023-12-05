from . import *
from libcst import matchers as m
from unittest import TestCase
from ast import literal_eval
from ..utils.is_referent_instance_of import IsNameReferentInstanceOfProvider

class TestStringInstanceOfProvider(TestCase):

    class NamedStringVisitor(m.MatcherDecoratableVisitor):
        METADATA_DEPENDENCIES = (IsNameReferentInstanceOfProvider[m.SimpleString],)

        @classmethod
        @property
        def matcher(cls):
            return m.SimpleString()

        def __init__(self) -> None:
            super().__init__()
            self.named_strings = set()
            self.collected_string_names = set()

        @m.visit(m.Assign(targets=[m.AssignTarget(target=m.Name()), m.ZeroOrMore()]))
        def register_assigned(self, node: cst.Assign) -> None:
            if m.matches(node.value, self.matcher):
                self.named_strings.add(node.targets[0].target.value)

        @m.visit(m.Name())
        def collect_names(self, node: cst.Name) -> None:
            if self.get_metadata(IsNameReferentInstanceOfProvider[m.SimpleString], node):
                self.collected_string_names.add(node.value)


    @classmethod
    def setUpClass(cls):
        ...

    def setUp(self):
        ...

    def visit_module(self, code: str) -> cst.Module:
        visitor = self.NamedStringVisitor()
        module = cst.parse_module(dedent(code).strip())
        wrapper = cst.metadata.MetadataWrapper(module)
        wrapper.visit(visitor)
        return wrapper, visitor

    def test_reifications_identical(self):
        first, second = IsNameReferentInstanceOfProvider[m.SimpleString], IsNameReferentInstanceOfProvider[m.SimpleString]
        assert first is second, "Reifications of parameterized class IsNameReferentInstanceOfProvider to parameter type str were not identical"

    def test_name_visitor_works(self):
        code = """
            s = "hi {}"
            t = s.format("world")
        """
        wrapper, visitor = self.visit_module(code)
        self.assertListEqual(["s"], list(visitor.named_strings), "NamedStringVisitor.named_strings does not contain expected name 's'")

    def test_provider_resolution(self):
        code = """
            s = "hi {}"
            t = s.format("world")
        """
        wrapper, visitor = self.visit_module(code)
        resolved = wrapper.resolve(visitor.METADATA_DEPENDENCIES[0])
        assert len(list(resolved.keys())) != 0, "Empty provider resolution"

    def test_visitor_metadata(self):
        code = """
            s = "hi {}"
            t = s.format("world")
        """
        wrapper, visitor = self.visit_module(code)
        self.assertListEqual(["s"], list(visitor.collected_string_names), f"Visitor collected_string_names doesn't match expected value ['s']: {visitor.collected_string_names}")

    # def test_provider_in_metadata_dict(self):
    #     code = """
    #         s = "hi {}"
    #         t = s.format("world")
    #     """
    #     wrapper, visitor = self.visit_module(code)
    #     assert IsNameReferentInstanceOfProvider[m.SimpleString] in visitor.metadata, f"Provider not in visitor metadata dict: {visitor.metadata}"
