import re

_NON_WORD = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    return _NON_WORD.sub("-", text.lower())
