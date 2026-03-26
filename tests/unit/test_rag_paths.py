from pathlib import Path

from ez_ax.rag.paths import LESSON_RAG_PATH, WORK_RAG_PATH


def test_rag_paths_match_canonical_repo_memory_locations() -> None:
    assert WORK_RAG_PATH == Path("docs/product/work-rag.json")
    assert LESSON_RAG_PATH == Path("docs/product/rag.json")


def test_rag_paths_are_relative_repo_paths() -> None:
    assert not WORK_RAG_PATH.is_absolute()
    assert not LESSON_RAG_PATH.is_absolute()


def test_no_third_canonical_memory_layer_exists() -> None:
    """Verify PRD constraint: only two canonical memory layers exist.

    PRD Canonical Memory Model section (lines 111-123) states:
    'Only two canonical memory layers exist. Current-state memory:
    docs/product/work-rag.json. Durable lesson memory: docs/product/rag.json.
    No third canonical memory layer exists.'

    This test verifies that the rag.paths module exports exactly two canonical
    memory paths and no additional memory layers.
    """
    # Import the paths module to inspect its namespace
    import ez_ax.rag.paths as rag_paths_module

    # Get all public attributes (those not starting with _)
    public_attrs = [
        name for name in dir(rag_paths_module) if not name.startswith("_")
    ]

    # Filter for Path objects (canonical memory paths)
    from pathlib import Path as PathClass

    memory_paths = [
        name
        for name in public_attrs
        if isinstance(getattr(rag_paths_module, name), PathClass)
    ]

    # Verify exactly two canonical memory paths exist
    assert len(memory_paths) == 2, (
        f"Expected exactly 2 canonical memory paths, found {len(memory_paths)}: "
        f"{memory_paths}"
    )

    # Verify the two paths are WORK_RAG_PATH and LESSON_RAG_PATH
    assert set(memory_paths) == {"WORK_RAG_PATH", "LESSON_RAG_PATH"}
