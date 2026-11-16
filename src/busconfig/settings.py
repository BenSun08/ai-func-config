"""Validated process-environment settings; never execute or auto-load .env files."""

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    ValidationError,
    field_validator,
)


class SettingsError(ValueError):
    """A safe settings diagnostic containing field names, never input values."""


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, hide_input_in_errors=True, allow_inf_nan=False)

    env: Literal["development", "test", "production"] = "development"
    data_dir: Path = Path("runtime/data")
    model_mode: Literal["disabled", "fake", "http"] = "disabled"
    model_base_url: str | None = None
    model_name: str | None = None
    model_timeout_seconds: float = Field(default=120, gt=0)
    model_transport_retries: int = Field(default=2, ge=0)
    model_schema_repairs: int = Field(default=1, ge=0)
    evidence_followups: int = Field(default=2, ge=0)
    model_concurrency: int = Field(default=1, gt=0)
    preparation_limit: int = Field(default=500, gt=0)
    search_max_nodes: int = Field(default=10000, gt=0)
    search_timeout_seconds: float = Field(default=30, gt=0)

    @field_validator("data_dir", mode="before")
    @classmethod
    def nonblank_data_dir(cls, value):
        if isinstance(value, str) and not value.strip():
            raise ValueError("data directory must not be blank")
        return value


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Read only supported fields, validating enabled features before use.

    Credentials are not needed by the local doctor and are not loaded into this
    object. T10/T11 will add secret-bearing settings at their owning boundaries.
    """
    environ = os.environ if environ is None else environ
    values = {
        field: environ[f"BUSCONFIG_{field.upper()}"]
        for field in Settings.model_fields
        if f"BUSCONFIG_{field.upper()}" in environ
    }
    try:
        settings = Settings.model_validate(values)
    except ValidationError as exc:
        fields = sorted({f"BUSCONFIG_{error['loc'][0].upper()}" for error in exc.errors()})
        raise SettingsError("Invalid settings: " + ", ".join(fields)) from None

    if settings.model_mode == "http":
        for field in ("model_base_url", "model_name"):
            value = getattr(settings, field)
            if not value or not value.strip() or value.strip().lower().startswith("replace-with-"):
                raise SettingsError(f"Configure BUSCONFIG_{field.upper()} for http mode")
        try:
            HttpUrl(settings.model_base_url)
        except ValidationError:
            raise SettingsError("Invalid settings: BUSCONFIG_MODEL_BASE_URL") from None
    return settings
