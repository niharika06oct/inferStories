"""Chapter text → structured claims extraction."""

from app.extraction.extract import extract_claims_from_text
from app.extraction.persist import (
    delete_replaceable_scene_claims,
    merge_extracted_claims_for_scene,
    persist_extracted_claims,
    replace_extracted_claims_for_scene,
)

__all__ = [
    "extract_claims_from_text",
    "delete_replaceable_scene_claims",
    "merge_extracted_claims_for_scene",
    "persist_extracted_claims",
    "replace_extracted_claims_for_scene",
]
