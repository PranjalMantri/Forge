from pathlib import Path
from typing import Any

import tomli
from config.config import Config
from platformdirs import user_config_dir
from util.errors import ConfigError
import logging

logger = logging.getLogger(__name__)

CONFIG_FILE_NAME = "config.toml"
AGENT_MD_FILE = "AGENT.md"


def get_config_dir() -> Path:
    return Path(user_config_dir("Forge"))


def get_system_config_file(cwd: Path) -> Path:
    return get_config_dir() / CONFIG_FILE_NAME


def _get_project_config(cwd: Path) -> Path | None:
    current = cwd.resolve()
    agent_dir = current / ".forge"

    if agent_dir.is_dir():
        config_file = agent_dir / CONFIG_FILE_NAME
        if config_file.is_file():
            return config_file

    return None


def _get_agent_md_file(cwd: Path) -> Path | None:
    current = cwd.resolve()

    if current.is_dir():
        agent_md_file = current / AGENT_MD_FILE
        if agent_md_file.is_file():
            content = agent_md_file.read_text(encoding="utf-8")
            return content

    return None


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_dict(result[key], value)
        else:
            result[key] = value

    return result


def _parse_toml(path: Path) -> dict[str, Any]:
    try:
        with open(path, "rb") as file:
            return tomli.load(file)
    except tomli.TOMLDecodeError as e:
        raise ConfigError(
            f"Invalid toml file in {path}: {e}", config_file=str(path)
        ) from e
    except (OSError, IOError) as e:
        raise ConfigError(
            f"Failed to read the fiel {path}: {e}", config_file=str(path)
        ) from e


def load_config(cwd: Path | None) -> Config:
    cwd = cwd or Path.cwd()

    system_config_path = get_system_config_file(cwd)

    config_dict: dict[str, Any] = {}

    if system_config_path.is_file():
        try:
            config_dict = _parse_toml(system_config_path)
        except ConfigError:
            logger.warning("Skippin invalid system config")

    project_config_path = _get_project_config(cwd)
    if project_config_path:
        try:
            project_config = _parse_toml(project_config_path)
            config_dict = _merge_dict(config_dict, project_config)
        except ConfigError:
            logger.warning("Skipping invalid system config")

    if "cwd" not in config_dict:
        config_dict["cwd"] = cwd

    if "developer_instructions" not in config_dict:
        agent_md_content = _get_agent_md_file(cwd)
        config_dict["developer_instructions"] = agent_md_content

    try:
        config = Config(**config_dict)
    except Exception as e:
        raise ConfigError(f"Invalid configuration: {e}")

    return config
