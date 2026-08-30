"""
Walks data/raw/{wiki,codex,chronicles,ephemera,[images]}/ and ingests every
file found, regardless of extension.

SKIP_OCR: OCR disabled by default -- see docs/limitations.md. Flip to False
to re-enable later on faster hardware.
"""

from pathlib import Path

from src.models.document import SourceType
from src.ingest.parse_document import ingest_file


SKIP_OCR = True

TOPIC_FOLDERS = {
    "wiki": SourceType.WIKI,
    "codex": SourceType.CODEX,
    "chronicles": SourceType.CHRONICLE,
    "ephemera": SourceType.EPHEMERA,
}
if not SKIP_OCR:
    TOPIC_FOLDERS["images"] = SourceType.IMAGE


def _is_ocr_file(file_path: Path) -> bool:
    if file_path.suffix.lower() in (".png", ".jpg", ".jpeg"):
        return True
    if file_path.name.lower().endswith(".scan.pdf"):
        return True
    return False


def ingest_corpus(raw_data_dir: str = "data/raw"):
    all_documents = []
    report = {"parsed_files": 0, "documents_created": 0, "needs_review": [],
               "failed": [], "skipped_ocr": [], "id_collisions": []}
    seen_doc_ids = set()

    for folder_name, source_type in TOPIC_FOLDERS.items():
        folder = Path(raw_data_dir) / folder_name
        if not folder.exists():
            continue

        for file_path in sorted(folder.rglob("*")):
            if not file_path.is_file():
                continue

            if SKIP_OCR and _is_ocr_file(file_path):
                report["skipped_ocr"].append(str(file_path))
                continue

            try:
                print(f"  parsing: {file_path.name}", flush=True)
                docs = ingest_file(str(file_path), source_type)

                for d in docs:
                    if d.doc_id in seen_doc_ids:
                        original_id = d.doc_id
                        counter = 2
                        while f"{original_id}_dup{counter}" in seen_doc_ids:
                            counter += 1
                        d.doc_id = f"{original_id}_dup{counter}"
                        report["id_collisions"].append({"original": original_id, "renamed_to": d.doc_id})
                    seen_doc_ids.add(d.doc_id)

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
    print(f"Skipped (OCR disabled): {len(report['skipped_ocr'])}")
    print(f"ID collisions auto-renamed: {len(report['id_collisions'])}")
    for c in report["id_collisions"]:
        print(f"  - {c['original']} -> {c['renamed_to']}")
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