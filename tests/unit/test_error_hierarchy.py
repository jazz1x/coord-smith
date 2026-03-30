from __future__ import annotations

from ez_ax.models.errors import (
    AppError,
    ConfigError,
    ExecutionTransportError,
    FlowError,
    ValidationError,
)


def test_error_hierarchy_subclasses_app_error() -> None:
    assert issubclass(ConfigError, AppError)
    assert issubclass(ValidationError, AppError)
    assert issubclass(FlowError, AppError)
    assert issubclass(ExecutionTransportError, AppError)
