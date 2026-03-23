from pathlib import Path

from ez_ax.rag.paths import LESSON_RAG_PATH, WORK_RAG_PATH


def test_rag_paths_match_canonical_repo_memory_locations() -> None:
    assert WORK_RAG_PATH == Path("docs/product/work-rag.json")
    assert LESSON_RAG_PATH == Path("docs/product/rag.json")


def test_rag_paths_are_relative_repo_paths() -> None:
    assert not WORK_RAG_PATH.is_absolute()
    assert not LESSON_RAG_PATH.is_absolute()
