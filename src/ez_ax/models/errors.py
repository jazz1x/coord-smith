"""Typed exception hierarchy for released-scope orchestration errors."""

from __future__ import annotations


class AppError(Exception):
    """Base class for typed ez-ax runtime errors."""


class ConfigError(AppError):
    """Raised when required configuration inputs are missing or invalid."""


class ValidationError(AppError):
    """Raised when a response violates a schema or evidence contract."""


class FlowError(AppError):
    """Raised when a request/response violates released-scope flow constraints."""


class ExecutionTransportError(AppError):
    """Raised when an OpenClaw invocation transport fails or returns malformed data."""
