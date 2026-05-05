"""Re-export shim — all symbols delegated to client.py to eliminate drift."""

from coord_smith.adapters.execution.client import (
    action_log_artifact_path,
    execute_within_scope,
    validate_action_log_artifacts_contain_ref_events,
    validate_action_log_artifacts_have_minimum_schema,
    validate_action_log_evidence_refs_resolvable,
    validate_release_ceiling_stop_action_log,
)

__all__ = [
    "action_log_artifact_path",
    "execute_within_scope",
    "validate_action_log_artifacts_contain_ref_events",
    "validate_action_log_artifacts_have_minimum_schema",
    "validate_action_log_evidence_refs_resolvable",
    "validate_release_ceiling_stop_action_log",
]
