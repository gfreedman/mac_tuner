"""
Config file loading for macaudit.

Reads ~/.config/macaudit/config.toml and returns structured config.
Never raises — always returns a valid dict with sensible defaults.
"""

from pathlib import Path

_CONFIG_PATH = Path.home() / ".config" / "macaudit" / "config.toml"


def load_config(path: Path | None = None) -> dict:
    """
    Load and return macaudit config from TOML file.

    Returns {"suppress": set[str]} — always valid, never raises.
    Missing file, parse errors, or bad shapes all return empty defaults.
    """
    config_path = path or _CONFIG_PATH
    empty: dict = {"suppress": set()}

    if not config_path.is_file():
        return empty

    try:
        raw = config_path.read_bytes()
    except OSError:
        return empty

    try:
        import tomllib
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError:
            return empty

    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except Exception:
        return empty

    suppress = data.get("suppress")
    if not isinstance(suppress, list):
        return empty

    return {"suppress": {str(item) for item in suppress}}
