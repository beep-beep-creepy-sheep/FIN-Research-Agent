from pathlib import Path

from app.document_store import DocumentStore, chunk_text, tokenize


def test_chunk_text_uses_overlap() -> None:
    text = "A" * 900 + "\n\n" + "cash flow improved. " * 80
    chunks = chunk_text(text, chunk_size=500, overlap=50)

    assert len(chunks) > 1
    assert chunks[0][1] == 0
    assert chunks[1][1] < chunks[0][2]


def test_tokenize_supports_english_and_chinese() -> None:
    assert tokenize("Apple 现金流 improved") == ["apple", "现金流", "improved"]


def test_document_store_indexes_and_searches(tmp_path: Path) -> None:
    report = tmp_path / "apple_2024.md"
    report.write_text(
        "# Apple 2024\n\nOperating cash flow increased while buybacks remained material.",
        encoding="utf-8",
    )
    store = DocumentStore(tmp_path / "library.sqlite")

    document_id = store.add_file(report)
    results = store.search("cash flow buybacks")

    assert document_id == 1
    assert results
    assert results[0].title == "apple_2024"
    assert "Operating cash flow" in results[0].text


def test_document_store_uses_fts_search(tmp_path: Path) -> None:
    report = tmp_path / "risk.md"
    report.write_text("Audit opinion mentioned impairment and revenue recognition.", encoding="utf-8")
    store = DocumentStore(tmp_path / "library.sqlite")
    store.add_file(report)

    results = store.search("impairment")

    assert results
    assert results[0].score > 0


def test_document_store_replaces_same_file(tmp_path: Path) -> None:
    report = tmp_path / "report.txt"
    report.write_text("first version revenue", encoding="utf-8")
    store = DocumentStore(tmp_path / "library.sqlite")

    first_id = store.add_file(report)
    report.write_text("second version cash flow", encoding="utf-8")
    second_id = store.add_file(report)

    assert second_id != first_id
    assert not store.search("revenue")
    assert store.search("cash flow")
