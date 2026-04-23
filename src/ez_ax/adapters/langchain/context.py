"""LangChain context bundle for graph-mediated calls."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LangChainContextBundle:
    """Structured context handed to LangChain from graph-owned state."""

    mission_name: str
    state_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    rag_refs: tuple[str, ...]
