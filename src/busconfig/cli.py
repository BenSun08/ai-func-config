"""Local command entry point."""

import argparse
import json
import os
import platform
import sys
from importlib.metadata import version
from tempfile import TemporaryFile

from busconfig.settings import Settings, SettingsError, load_settings


def redact(text: str) -> str:
    """Scrub configured credentials before JSON escaping diagnostic text."""
    secrets = {
        value
        for name, value in os.environ.items()
        if name.startswith("BUSCONFIG_")
        and value
        and any(marker in name for marker in ("KEY", "SECRET", "TOKEN", "PASSWORD", "URL"))
    }
    for secret in sorted(secrets, key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    return text


def doctor(settings: Settings) -> int:
    """Report local readiness without connecting to a model or database.

    Use an explicit output allowlist: URLs, model names, credentials and raw
    settings/exception representations must not enter diagnostics.
    """
    writable = False
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        with TemporaryFile(dir=settings.data_dir) as probe:
            probe.write(b"busconfig doctor\n")
            probe.flush()
        writable = True
    except OSError:
        pass  # The structured failure below avoids exposing exception contents.

    report = {
        "versions": {
            "python": platform.python_version(),
            "busconfig": version("ai-func-config"),
            **{
                name: version(name)
                for name in (
                    "pydantic",
                    "openpyxl",
                    "python-docx",
                    "pyyaml",
                    "httpx",
                )
            },
        },
        "environment": settings.env,
        "model_mode": settings.model_mode,
        "data_dir": {"path": redact(str(settings.data_dir)), "writable": writable},
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if writable else 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="busconfig")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Check local versions, settings and writable data directory")
    parser.parse_args(argv)
    try:
        settings = load_settings()
    except SettingsError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return doctor(settings)


if __name__ == "__main__":
    raise SystemExit(main())
