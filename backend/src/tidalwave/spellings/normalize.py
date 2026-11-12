from __future__ import annotations

import re
import unicodedata

_UNDECOMPOSED = str.maketrans({"ø": "o", "æ": "ae", "œ": "oe", "ł": "l", "đ": "d", "ð": "d"})
_FEATURING = re.compile(r"\s*[(\[]?\s*\b(?:feat|ft|featuring)\b\.?\s.*$")
_LEADING_THE = re.compile(r"^\s*the\s+")
_VERSION_SUFFIX = re.compile(r"\s+-\s+.*$|\s*[(\[].*$")
_NOT_A_LETTER = re.compile(r"[\W_]+")


def _fold(name: str) -> str:
    stripped = "".join(
        c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c)
    )
    return stripped.casefold().translate(_UNDECOMPOSED)


def spelling_key(name: str) -> str:
    folded = _FEATURING.sub("", _fold(name))
    folded = _LEADING_THE.sub("", folded.replace("&", " and "))
    return _NOT_A_LETTER.sub("", folded) or name.casefold()


def track_key(title: str) -> str:
    folded = _VERSION_SUFFIX.sub("", _fold(title))
    return _NOT_A_LETTER.sub("", folded) or title.casefold()
