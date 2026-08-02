from pathlib import Path
from typing import Any

from config.config import Config
from config.loader import get_config_dir
from tools.base import Tool
from tools.registry import ToolRegistry
from tools.subagent import SubAgentDefinition, SubAgentTool
import importlib.util
import sys
import inspect


class ToolDiscoveryManager:
    def __init__(self, config: Config, registry: ToolRegistry):
        self.config = config
        self.registry = registry

    def _load_tool_modules(self, file_path: Path) -> Any:
        module_name = f"discovered_tool_{file_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)

        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module: {file_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module

        spec.loader.exec_module(module)
        return module

    def _find_tool_classes(self, module: Any) -> list[Tool]:
        tools: list[Tool] = []

        for name in dir(module):
            obj = getattr(module, name)

            if (
                inspect.isclass(obj)
                and issubclass(obj, Tool)
                and obj is not Tool
                and obj.__module__ == module.__name__
            ):
                tools.append(obj)

        return tools

    def _find_subagent_definitions(self, module: Any) -> list[SubAgentDefinition]:
        definitions: list[SubAgentDefinition] = []

        for name in dir(module):
            obj = getattr(module, name)

            if (isinstance(obj, SubAgentDefinition)):
                definitions.append(obj)

        return definitions

    def discover_from_dir(self, directory: Path) -> None:
        tool_dir = directory / ".forge" / "tools"

        if tool_dir.exists() and tool_dir.is_dir():
            for py_file in tool_dir.glob("*.py"):
                try:
                    if py_file.name.startswith("__"):
                        continue

                    module = self._load_tool_modules(py_file)
                    tool_classes = self._find_tool_classes(module)

                    if not tool_classes:
                        continue

                    for tool_class in tool_classes:
                        tool = tool_class(self.config)
                        self.registry.register(tool)
                except:
                    pass

        subagent_dir = directory / ".forge" / "subagents"

        if subagent_dir.exists() and subagent_dir.is_dir():
            for py_file in subagent_dir.glob("*.py"):
                try:
                    if py_file.name.startswith("__"):
                        continue

                    module = self._load_tool_modules(py_file)
                    subagent_defs = self._find_subagent_definitions(module)

                    if not subagent_defs:
                        continue

                    for definition in subagent_defs:
                        self.registry.register(
                            SubAgentTool(config=self.config, definition=definition)
                        )
                except:
                    pass

    def discover_all(self):
        self.discover_from_dir(self.config.cwd)
        self.discover_from_dir(get_config_dir())
