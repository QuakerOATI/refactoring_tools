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
