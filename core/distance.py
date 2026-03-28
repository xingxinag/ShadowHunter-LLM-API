from __future__ import annotations

from math import sqrt
import re


def cosine_distance(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = sqrt(sum(a * a for a in left))
    right_norm = sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 1.0
    value = 1.0 - max(-1.0, min(1.0, numerator / (left_norm * right_norm)))
    return 0.0 if abs(value) < 1e-12 else round(value, 6)


def markdown_tag_set(text: str) -> set[str]:
    tags: set[str] = set()
    if re.search(r"^#+\s", text, flags=re.MULTILINE):
        tags.add("heading")
    if re.search(r"^[-*+]\s", text, flags=re.MULTILINE):
        tags.add("list")
    if "```" in text:
        tags.add("code")
    if re.search(r"^>\s", text, flags=re.MULTILINE):
        tags.add("quote")
    return tags


def structural_distance(left: str, right: str) -> float:
    left_tags = markdown_tag_set(left)
    right_tags = markdown_tag_set(right)
    if not left_tags and not right_tags:
        return 0.0
    union = left_tags | right_tags
    intersection = left_tags & right_tags
    return round(1 - (len(intersection) / len(union)), 6)


def combined_distance(semantic: float, structural: float) -> float:
    return round(0.8 * semantic + 0.2 * structural, 6)


def simple_text_embedding(text: str) -> list[float]:
    tokens = text.split()
    length = len(text)
    unique = len(set(tokens))
    code_fence = text.count("```")
    return [float(length), float(unique), float(code_fence + 1)]


def multimodal_distance(left: str, right: str) -> float:
    semantic = cosine_distance(simple_text_embedding(left), simple_text_embedding(right))
    structural = structural_distance(left, right)
    return combined_distance(semantic, structural)
