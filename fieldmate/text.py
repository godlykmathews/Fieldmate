"""Keep model formatting out of chat prose and the speech synthesizer."""

import re


def plain_text(text):
    # Source cards retain citations/URLs; prose should read naturally on its own.
    text = re.sub(r"!?\[([^\]\n]+)\]\(https?://[^\s)]+\)", r"\1", text)
    text = re.sub(r"(?<![\w=])\[(?:D\d+|web-\d+|\d+)(?:\s*[,;]\s*(?:D\d+|web-\d+))*\]", "", text)
    text = re.sub(r"(?m)^\s{0,3}(?:`{3,}|~{3,})[^\n]*$", "", text)
    text = re.sub(r"(?m)^\s{0,3}(?:[-*_][ \t]*){3,}$", "", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}[ \t]+|^\s{0,3}>[ \t]+", "", text)
    text = re.sub(r"(?m)^[ \t]*[-+*•][ \t]+(?:\[[ xX]\][ \t]+)?", "", text)
    for marker in (r"\*\*", "__", "~~"):
        text = re.sub(r"(?<!\w)" + marker + r"(\S(?:.*?\S)?)" + marker + r"(?!\w)", r"\1", text, flags=re.S)
    text = re.sub(r"(?<!\w)\*([^\s*](?:[^*\n]*[^\s*])?)\*(?!\w)", r"\1", text)
    text = re.sub(r"(?<!\w)_([^\s_](?:[^_\n]*[^\s_])?)_(?!\w)", r"\1", text)
    text = text.replace("`", "")
    text = re.sub(r"[ \t]+([,.!?;:])", r"\1", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def speech_text(text):
    text = plain_text(text)
    text = re.sub(r"https?://\S+", "the linked source", text)
    # Preserve math meaning instead of deleting operators with the formatting.
    replacements = {
        "**": " to the power of ",
        "×": " times ",
        "*": " times ",
        "÷": " divided by ",
        "/": " divided by ",
        "+": " plus ",
        "=": " equals ",
        "≤": " less than or equal to ",
        "≥": " greater than or equal to ",
        "<": " less than ",
        ">": " greater than ",
        "^": " to the power of ",
        "%": " percent ",
        "&": " and ",
        "°": " degrees ",
        "→": " to ",
    }
    for symbol, words in replacements.items():
        text = text.replace(symbol, words)
    text = re.sub(r"[\[\]{}()|#~_•]", " ", text)
    return re.sub(r"\s+", " ", text).strip()
