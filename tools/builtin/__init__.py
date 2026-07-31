__ALL__ = ["ReadFileTool", "WriteFileTool", "EditFileTool", "ShellTool"]

from tools.base import Tool
from tools.builtin.read_file import ReadFileTool
from tools.builtin.write_file import WriteFileTool
from tools.builtin.edit_file import EditFileTool
from tools.builtin.shell import ShellTool


def get_all_tools() -> list[Tool]:
    return [ReadFileTool, WriteFileTool, EditFileTool, ShellTool]
