"""
deduplication.subject_group
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Helper to compute a stable subject-group identifier to avoid duplicate processing
of emails belonging to the same conversation/business intent.
"""
from __future__ import annotations

import hashlib
import re
from utils.text_helpers import (
    normalize_no_accents_lower_trim as _normalize_no_accents_lower_trim,
    strip_leading_reply_prefixes as _strip_leading_reply_prefixes,
)


def generate_subject_group_id(subject: str) -> str:
    """Return a stable identifier for a subject line.

    Heuristic:
    - Normalize subject (remove accents, lowercase, collapse spaces)
    - Strip leading reply/forward prefixes
    - If looks like Média Solution Missions Recadrage with a 'lot <num>' →
      "media_solution_missions_recadrage_lot_<num>"
    - Else if any 'lot <num>' is present → "lot_<num>"
    - Else fallback to hash of the normalized subject
    """
    norm = _normalize_no_accents_lower_trim(subject or "")
    core = _strip_leading_reply_prefixes(norm)

    # Try to extract lot number
    m_lot = re.search(r"\blot\s+(\d+)\b", core)
    lot_part = m_lot.group(1) if m_lot else None

    # Detect Média Solution Missions Recadrage keywords
    is_media_solution = all(tok in core for tok in ["media solution", "missions recadrage", "lot"]) if core else False

    if is_media_solution and lot_part:
        return f"media_solution_missions_recadrage_lot_{lot_part}"
    if lot_part:
        return f"lot_{lot_part}"

    # Fallback: hash the core subject
    subject_hash = hashlib.md5(core.encode("utf-8")).hexdigest()
    return f"subject_hash_{subject_hash}"
