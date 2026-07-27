__ALL__ = ["ReadFileTool"]

from tools.base import Tool
from tools.builtin.read_file import ReadFileTool


def get_all_tools() -> list[Tool]:
    return [ReadFileTool]
