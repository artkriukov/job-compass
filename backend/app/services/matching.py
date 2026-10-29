import re

from app.models import SearchRequest

TOKEN_RE = re.compile(r"[\w+#.-]+", re.UNICODE)


def tokens(value: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(value) if len(token) > 1}


def score_text(text: str, request: SearchRequest) -> tuple[int, str] | None:
    haystack = text.lower()
    if any(keyword in haystack for keyword in request.exclude_keywords):
        return None

    role_tokens = tokens(request.role)
    found_role = role_tokens.intersection(tokens(haystack))
    role_score = int(70 * len(found_role) / max(len(role_tokens), 1))
    included = [keyword for keyword in request.include_keywords if keyword in haystack]
    include_score = int(25 * len(included) / max(len(request.include_keywords), 1))
    score = min(100, role_score + include_score + (5 if found_role else 0))
    if not found_role or score < 25:
        return None

    parts = [f"совпали слова должности: {', '.join(sorted(found_role))}"]
    if included:
        parts.append(f"ключевые слова: {', '.join(included)}")
    return score, "; ".join(parts)

