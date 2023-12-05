from textwrap import dedent
from unittest.mock import Mock

import libcst as cst
from libcst.codemod import CodemodContext, CodemodTest
from libcst.metadata import MetadataWrapper

from ..codemods import (
    AddGlobalStatements,
    RemoveLogfuncDefAndImports,
    ReplaceFuncWithLoggerCommand,
)
