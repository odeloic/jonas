"""Telegram MarkdownV2 formatting utilities.

Telegram's MarkdownV2 requires escaping 18 special characters outside of
formatting markers. Helpers here handle escaping and provide composable
formatting primitives, plus a markdown-to-MarkdownV2 converter for LLM output.

Reference: https://core.telegram.org/bots/api#markdownv2-style
"""

import re

_ESCAPE_RE = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")


def escape(text: str) -> str:
    """Escape special characters for MarkdownV2 (outside formatting markers)."""
    return _ESCAPE_RE.sub(r"\\\1", text)


def bold(text: str) -> str:
    """Wrap already-escaped text in bold markers."""
    return f"*{text}*"


def italic(text: str) -> str:
    """Wrap already-escaped text in italic markers."""
    return f"_{text}_"


def _convert_inline(text: str) -> str:
    """Convert standard markdown inline formatting to MarkdownV2.

    Processes ***bold-italic***, **bold**, *italic*, and `code` spans.
    Escapes all plain text segments between them.

    Uses a character-by-character scan to correctly handle nesting
    (e.g. *italic with **bold** inside*).
    """
    result: list[str] = []
    i = 0
    n = len(text)

    while i < n:
        # `code`
        if text[i] == "`":
            end = text.find("`", i + 1)
            if end != -1:
                result.append(f"`{text[i + 1 : end]}`")
                i = end + 1
                continue

        # *** bold-italic ***
        if text[i : i + 3] == "***":
            end = text.find("***", i + 3)
            if end != -1:
                inner = _convert_inline(text[i + 3 : end])
                result.append(f"*_{inner}_*")
                i = end + 3
                continue

        # ** bold **
        if text[i : i + 2] == "**":
            end = text.find("**", i + 2)
            if end != -1:
                inner = _convert_inline(text[i + 2 : end])
                result.append(f"*{inner}*")
                i = end + 2
                continue

        # * italic * — find matching *, handling nested **
        if text[i] == "*":
            # Scan for closing * that isn't part of **
            j = i + 1
            found = -1
            while j < n:
                if text[j : j + 2] == "**":
                    # Skip past nested **...**
                    close = text.find("**", j + 2)
                    if close != -1:
                        j = close + 2
                    else:
                        j += 2
                elif text[j] == "*":
                    found = j
                    break
                else:
                    j += 1
            if found != -1:
                inner = _convert_inline(text[i + 1 : found])
                result.append(f"_{inner}_")
                i = found + 1
                continue

        # Plain character — escape it
        result.append(escape(text[i]))
        i += 1

    return "".join(result)


def _convert_line(line: str) -> str:
    """Convert a single line of standard markdown to MarkdownV2."""
    # Headings: # Title → *Title* (bold, Telegram has no heading syntax)
    heading_match = re.match(r"^(#{1,3})\s+(.+)$", line)
    if heading_match:
        return bold(_convert_inline(heading_match.group(2)))

    # Unordered list items: - text → • text
    list_match = re.match(r"^(\s*)-\s+(.+)$", line)
    if list_match:
        indent = escape(list_match.group(1))
        return f"{indent}• {_convert_inline(list_match.group(2))}"

    # Table rows: | a | b | → a | b (simplified, escape cells)
    if line.startswith("|") and line.endswith("|"):
        # Skip separator rows like |---|---|
        if re.match(r"^\|[\s\-:|]+\|$", line):
            return ""
        cells = [c.strip() for c in line.strip("|").split("|")]
        converted = " \\| ".join(_convert_inline(c) for c in cells)
        return converted

    return _convert_inline(line)


def md_to_telegram(text: str) -> str:
    """Convert standard markdown (from LLM output) to Telegram MarkdownV2.

    Handles: **bold**, *italic*, `code`, # headings, - lists, | tables |.
    Escapes all other special characters.
    """
    lines = text.split("\n")
    converted = [_convert_line(line) for line in lines]
    # Remove empty lines from table separators but keep intentional blank lines
    return "\n".join(converted)


def format_correction(
    *,
    has_error: bool,
    corrected: str | None,
    explanation: str,
    follow_up: str,
    error_type: str | None = None,
) -> str:
    """Build a MarkdownV2 formatted correction reply.

    All input strings are raw (unescaped) — this function handles escaping.
    """
    parts: list[str] = []

    if has_error and corrected:
        parts.append(f"✏️ {bold(escape(corrected))}")
        if error_type:
            parts.append(italic(escape(f"Fehlertyp: {error_type}")))
        parts.append("")
        parts.append(escape(explanation))
    else:
        parts.append(f"✅ {escape(explanation)}")

    parts.append("")
    parts.append(italic(escape(follow_up)))
    return "\n".join(parts)
