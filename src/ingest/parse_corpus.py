"""
Walks data/raw/{wiki,codex,chronicles,ephemera}/ and ingests EVERY file
found in each folder, regardless of extension. This is the file that
actually proves the fix: it does not assume "codex folder = .docx files."
It looks at what's actually there and reads each file according to its own
extension via ingest_file() -> read_any().
"""

from pathlib import Path

from src.models.document import SourceType
from src.ingest.parse_document import ingest_file


TOPIC_FOLDERS = {
    "wiki": SourceType.WIKI,
    "codex": SourceType.CODEX,
    "chronicles": SourceType.CHRONICLE,
    "ephemera": SourceType.EPHEMERA,
}


def ingest_corpus(raw_data_dir: str = "data/raw"):
    """Returns (all_documents, ingestion_report). The report is important --
    it tells you what got parsed, what needed heuristic splitting (i.e.
    might be wrong and worth spot-checking), and any files that failed
    outright so nothing silently vanishes from your corpus."""
    all_documents = []
    report = {"parsed_files": 0, "documents_created": 0, "needs_review": [], "failed": []}

    for folder_name, source_type in TOPIC_FOLDERS.items():
        folder = Path(raw_data_dir) / folder_name
        if not folder.exists():
            continue

        for file_path in sorted(folder.rglob("*")):
            if not file_path.is_file():
                continue
            try:
                docs = ingest_file(str(file_path), source_type)
                all_documents.extend(docs)
                report["parsed_files"] += 1
                report["documents_created"] += len(docs)
                for d in docs:
                    if d.metadata.get("needs_review"):
                        report["needs_review"].append(d.doc_id)
            except Exception as e:
                report["failed"].append({"file": str(file_path), "error": str(e)})

    return all_documents, report


if __name__ == "__main__":
    docs, report = ingest_corpus()

    print(f"Files parsed:      {report['parsed_files']}")
    print(f"Documents created: {report['documents_created']}")
    print(f"Needs manual review (heuristic split, verify these): {len(report['needs_review'])}")
    for doc_id in report["needs_review"]:
        print(f"  - {doc_id}")
    print(f"Failed: {len(report['failed'])}")
    for f in report["failed"]:
        print(f"  - {f['file']}: {f['error']}")

    print("\n--- Sample of parsed documents ---")
    for d in docs[:8]:
        print(f"[{d.source_type.value:10s}] {d.doc_id:45s} reliability={d.reliability_prior} "
              f"entities={len(d.entities)} tables={len(d.tables)} chars={len(d.raw_text)}")
