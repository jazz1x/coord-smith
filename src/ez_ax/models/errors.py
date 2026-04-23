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


class AccessibilityPermissionDenied(ExecutionTransportError):
    """Mouse control silently fails (macOS Accessibility permission missing)."""


class ScreenCapturePermissionDenied(ExecutionTransportError):
    """Screen capture refused by OS (macOS Screen Recording permission missing)."""


class ScreenCaptureUnavailable(ExecutionTransportError):
    """Screenshot attempt failed for a reason other than permission denial."""


class ClickExecutionUnverified(ExecutionTransportError):
    """pyautogui.click succeeded silently but the cursor did not reach the target."""


class ClickCoordinatesOutOfBounds(ExecutionTransportError):
    """Requested click coordinates fall outside the detected screen size."""
