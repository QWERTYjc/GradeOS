#!/usr/bin/env python
import argparse
import json
import re
import sys
from typing import Dict, List

PATTERNS: Dict[str, List[str]] = {
    "missing_env": [
        r"missing (required )?environment variable",
        r"environment variable .* (not set|missing)",
        r"process\.env\.[A-Z0-9_]+",
        r"\b[A-Z0-9_]+\b (is|was) not set",
    ],
    "build_failed": [
        r"build failed",
        r"npm ERR!",
        r"yarn .*error",
        r"pnpm .*ERR",
        r"exit code 1",
    ],
    "crash_loop": [
        r"exited with code",
        r"crashloop",
        r"restarting",
    ],
    "oom": [
        r"out of memory",
        r"heap out of memory",
        r"exit code 137",
        r"killed process",
    ],
    "connection_error": [
        r"ECONNREFUSED",
        r"ENOTFOUND",
        r"EAI_AGAIN",
        r"connection refused",
        r"getaddrinfo",
    ],
    "tls_error": [
        r"CERT_",
        r"self signed",
        r"ssl",
        r"tls",
    ],
    "migration_error": [
        r"prisma",
        r"sequelize",
        r"migration",
        r"relation .* does not exist",
        r"SQLSTATE",
    ],
    "permission_error": [
        r"EACCES",
        r"permission denied",
    ],
}

DEFAULT_ERROR_HINTS = [
    r"error",
    r"exception",
    r"fatal",
    r"panic",
    r"traceback",
]


def read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def scan_lines(lines: List[str], max_lines: int) -> Dict[str, List[str]]:
    matches: Dict[str, List[str]] = {}
    for category, patterns in PATTERNS.items():
        for line in lines:
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    matches.setdefault(category, [])
                    if len(matches[category]) < max_lines:
                        matches[category].append(line.strip())
                    break
    return matches


def find_generic_errors(lines: List[str], max_lines: int) -> List[str]:
    results: List[str] = []
    for line in lines:
        for pattern in DEFAULT_ERROR_HINTS:
            if re.search(pattern, line, re.IGNORECASE):
                if len(results) < max_lines:
                    results.append(line.strip())
                break
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan logs for common error patterns.")
    parser.add_argument("path", nargs="?", default="-", help="Path to log file or '-' for stdin")
    parser.add_argument("--max-lines", type=int, default=3, help="Max lines per category")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    text = read_text(args.path)
    lines = text.splitlines()

    matches = scan_lines(lines, args.max_lines)
    generic = find_generic_errors(lines, args.max_lines)

    result = {
        "matched_categories": sorted(matches.keys()),
        "matches": matches,
        "generic_error_lines": generic if not matches else [],
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if not matches and not generic:
            print("No obvious error patterns found.")
            return 0
        for category in sorted(matches.keys()):
            print(f"[{category}]")
            for line in matches[category]:
                print(f"  {line}")
        if generic and not matches:
            print("[generic_error_lines]")
            for line in generic:
                print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
