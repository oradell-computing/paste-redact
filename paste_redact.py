#!/usr/bin/env python3
# Required Notice: Copyright (c) 2026 Wick McLean (https://github.com/oradell-computing)
# Licensed under the PolyForm Small Business License 1.0.0:
# https://polyformproject.org/licenses/small-business/1.0.0
"""Mask sensitive values in text before pasting it into a chat, issue or forum.

Reads stdin, writes the redacted text to stdout (and nothing else); warnings go to stderr.

Your own terms live in ~/.config/paste-redact/terms.txt (override the path with the
PASTE_REDACT_TERMS environment variable), one per line:
    secret-text             -> replaced with REDACTED
    secret-text => LABEL    -> replaced with LABEL (the separator is " => ", with spaces)
    secret-text ==> LABEL   -> the same, but the secret must match with exact case
    # comment               -> ignored
A line with neither " => " nor " ==> " is one plain term, even if it contains "=". If a line
has both, the first one splits it. Whitespace around the secret and the label is stripped.
Terms are matched longest first (both kinds together) and applied before the built-in
patterns. Plain terms and "=>" terms ignore case; "==>" terms do not.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

__version__ = "0.3.0"

LABEL_SEPARATOR = " => "  # case-insensitive term
CASE_SENSITIVE_SEPARATOR = " ==> "
DEFAULT_TERMS = "~/.config/paste-redact/terms.txt"

PATTERNS = [
    (
        re.compile(r"\b(state|code|code_challenge|code_verifier)=[^&\s]+"),
        r"\1=REDACTED",
    ),
    (re.compile(r"\b(AKIA|ASIA)[A-Z0-9]{16}\b"), "ACCESS_KEY_ID"),
    (
        re.compile(
            r"(?i)(secret_access_key|SecretAccessKey)([\"'\s:=]+)[A-Za-z0-9/+=]{40}"
        ),
        r"\1\2SECRET_KEY",
    ),
    (re.compile(r"[A-Za-z0-9/+=_-]{100,}"), "LONG_TOKEN"),
    (
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
        "PRIVATE_KEY",
    ),
    (
        re.compile(
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
        ),
        "UUID",
    ),
    (re.compile(r"(?<!\d)\d{12}(?!\d)"), "ACCOUNT"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "EMAIL"),
    (
        re.compile(r"\b(?!127\.0\.0\.1\b)(?!0\.0\.0\.0\b)(?:\d{1,3}\.){3}\d{1,3}\b"),
        "IP",
    ),
]


def warn(message: str) -> None:
    print(f"paste-redact: warning: {message}", file=sys.stderr)


def terms_path() -> str:
    # An empty variable counts as unset, so `PASTE_REDACT_TERMS=` falls back to the default.
    return os.path.expanduser(os.environ.get("PASTE_REDACT_TERMS") or DEFAULT_TERMS)


def split_term(line: str) -> tuple[str, str, bool]:
    """Split a line into (secret, label, case_sensitive); the earliest separator wins."""
    found = [
        (line.index(sep), sep, case_sensitive)
        for sep, case_sensitive in (
            (LABEL_SEPARATOR, False),
            (CASE_SENSITIVE_SEPARATOR, True),
        )
        if sep in line
    ]
    if not found:  # a plain term, "=" and all
        return line, "", False
    index, sep, case_sensitive = min(found)
    return line[:index], line[index + len(sep) :], case_sensitive


def parse_terms(lines: list[str]) -> list[tuple[str, str, bool]]:
    """Turn terms-file lines into (secret, label, case_sensitive), longest secret first."""
    terms = []
    for line in lines:
        line = line.rstrip(
            "\r\n"
        )  # CRLF files (Windows editors) must not leave a "\r" in the term
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        secret, label, case_sensitive = split_term(line)
        secret, label = secret.strip(), label.strip()
        if not secret:
            warn(
                "terms file: ignored a line with an empty secret before ' => ' or ' ==> '"
            )
            continue
        terms.append((secret, label or "REDACTED", case_sensitive))
    return sorted(terms, key=lambda t: len(t[0]), reverse=True)


def load_terms(path: str) -> list[tuple[str, str, bool]]:
    """Read the terms file. A missing file only warns; any other failure stops the run.

    Stopping is deliberate: carrying on would print text that still contains the secrets
    the user asked to have removed.
    """
    try:
        # utf-8-sig drops the byte-order mark some editors (Notepad++) add.
        with open(path, encoding="utf-8-sig") as f:
            return parse_terms(f.readlines())
    except FileNotFoundError:
        warn(f"terms file not found: {path} (only the built-in patterns were applied)")
        return []
    except (OSError, UnicodeDecodeError) as error:
        sys.exit(f"paste-redact: error: cannot read terms file {path}: {error}")


def read_input() -> str:
    data = sys.stdin.buffer.read()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        warn("input is not valid UTF-8; invalid bytes were replaced with U+FFFD")
        return data.decode("utf-8", errors="replace")


def redact(text: str, terms: list[tuple[str, str, bool]]) -> str:
    for secret, label, case_sensitive in terms:
        # Double the backslashes so a label like C:\work is inserted literally, not as an escape.
        text = re.sub(
            re.escape(secret),
            label.replace("\\", "\\\\"),
            text,
            flags=0 if case_sensitive else re.IGNORECASE,
        )
    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="paste-redact",
        description="Read text on stdin and write it to stdout with sensitive values masked. "
        "Your own terms are read from the file named by PASTE_REDACT_TERMS, "
        f"or {DEFAULT_TERMS}.",
        allow_abbrev=False,
    )


def main() -> None:
    parser = build_parser()
    parser.add_argument(
        "--version", action="version", version=f"paste-redact {__version__}"
    )
    parser.parse_args()  # only --help and --version exist; anything else is an error
    terms = load_terms(terms_path())
    text = redact(read_input(), terms)
    # Bytes, not text: no newline translation and no dependence on the terminal's locale.
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
