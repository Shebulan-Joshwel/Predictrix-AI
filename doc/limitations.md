## Known limitation: OCR pipeline unverified in local dev environment

The ingestion pipeline includes OCR support (tesseract + pymupdf) for
standalone images and scanned-page PDFs, covering ~102 of 415 corpus files.
This path could not be fully verified in our Windows dev environment due to
persistent tooling/PATH issues, despite tesseract installing successfully.

Impact: ~102 files (mostly portrait/heraldry/creature images and a handful
of scanned ephemera) may not contribute to retrieval. Since our track is
1C (fact-lookup and multi-step reasoning), and image-only facts largely
overlap with codex register-table data already captured in text form, we
assess this as low-impact for our specific sub-track, though not zero-risk.

If time permits in the final days, revisit on a different environment
(WSL/Linux) where the OCR toolchain is simpler to configure.