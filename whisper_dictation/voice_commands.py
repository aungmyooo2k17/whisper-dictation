"""
Spoken punctuation and voice commands.
Converts spoken words like "period" into punctuation characters.
"""

import re

# Spoken punctuation -> character mappings
BUILTIN_COMMANDS = {
    "period": ".",
    "full stop": ".",
    "comma": ",",
    "question mark": "?",
    "exclamation mark": "!",
    "exclamation point": "!",
    "colon": ":",
    "semicolon": ";",
    "dash": "\u2014",
    "hyphen": "-",
    "ellipsis": "...",
    "open quote": '"',
    "close quote": '"',
    "open paren": "(",
    "close paren": ")",
    "new line": "\n",
    "new paragraph": "\n\n",
    "tab": "\t",
    "ampersand": "&",
    "at sign": "@",
    "hashtag": "#",
    "dollar sign": "$",
    "percent sign": "%",
    "asterisk": "*",
    "underscore": "_",
    "plus sign": "+",
    "equals sign": "=",
    "slash": "/",
    "backslash": "\\",
}

# Characters that attach to the previous word (no leading space)
_ATTACH_LEFT = set('.,?!:;')

# Action commands that modify the text
ACTION_COMMANDS = {
    "delete that": "_ACTION_DELETE_LAST",
    "scratch that": "_ACTION_DELETE_LAST",
    "undo that": "_ACTION_DELETE_LAST",
}


def _delete_last_clause(text: str) -> str:
    """Remove the last sentence or clause from text."""
    text = text.rstrip()
    if not text:
        return text

    # Find the last sentence boundary
    for i in range(len(text) - 1, -1, -1):
        if text[i] in ".!?\n":
            return text[: i + 1] + " "
    # No boundary found - delete everything
    return ""


def apply_voice_commands(text: str, custom_commands: list = None) -> str:
    """Apply voice commands and spoken punctuation to transcribed text.

    Args:
        text: Raw transcribed text.
        custom_commands: List of {"from": str, "to": str} dicts for custom replacements.

    Returns:
        Text with voice commands applied.
    """
    if not text:
        return text

    # Build combined command map (custom overrides builtins)
    commands = dict(BUILTIN_COMMANDS)
    if custom_commands:
        for cmd in custom_commands:
            if "from" in cmd and "to" in cmd:
                commands[cmd["from"].lower()] = cmd["to"]

    # Process action commands first
    for action_phrase, action_type in ACTION_COMMANDS.items():
        pattern = re.compile(re.escape(action_phrase), re.IGNORECASE)
        while pattern.search(text):
            match = pattern.search(text)
            before = text[: match.start()].rstrip()
            after = text[match.end() :].lstrip()
            if action_type == "_ACTION_DELETE_LAST":
                before = _delete_last_clause(before)
            text = before + after

    # Build a single regex that matches any command phrase (longest first)
    sorted_keys = sorted(commands.keys(), key=len, reverse=True)
    # Escape each key for regex and join with |
    alternatives = "|".join(re.escape(k) for k in sorted_keys)
    combined_pattern = re.compile(
        r'(?:\s*)(?:' + alternatives + r')(?:\s*)',
        re.IGNORECASE,
    )

    # Single-pass replacement using a lookup function
    def _replace_match(m):
        # Extract just the command word (strip surrounding whitespace from the match)
        matched_text = m.group(0).strip().lower()
        replacement = commands.get(matched_text, matched_text)

        if replacement in _ATTACH_LEFT:
            # Punctuation: attach to previous word, add trailing space
            return replacement + " "
        if replacement in ("\n", "\n\n", "\t"):
            # Whitespace commands: just the replacement
            return replacement
        if replacement in ("(", '"') and m.start() > 0:
            # Opening brackets: space before
            return " " + replacement
        if replacement in (")", '"'):
            # Closing brackets: no leading space
            return replacement + " "
        # Default: space-separated
        return " " + replacement + " "

    # We need word-boundary matching. Rebuild with word boundaries.
    combined_pattern = re.compile(
        r'\s*\b(?:' + alternatives + r')\b\s*',
        re.IGNORECASE,
    )

    # Do replacement in one pass from left to right
    result_parts = []
    last_end = 0
    for m in combined_pattern.finditer(text):
        # Add text before this match
        result_parts.append(text[last_end:m.start()])
        # Add the replacement
        result_parts.append(_replace_match(m))
        last_end = m.end()
    # Add remaining text
    result_parts.append(text[last_end:])
    text = "".join(result_parts)

    # Clean up multiple spaces (but not newlines)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    # Clean up space before punctuation
    text = re.sub(r' +([.,?!:;])', r'\1', text)
    # Clean up space before newlines
    text = re.sub(r' +\n', '\n', text)
    # Clean up space after opening brackets
    text = re.sub(r'(\() ', r'\1', text)
    # Clean up space before closing brackets
    text = re.sub(r' (\))', r'\1', text)

    return text.strip()
