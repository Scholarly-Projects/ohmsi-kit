import argparse
import csv
import re
import shutil
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REPLACEMENT_SPEAKER = "Interviewee"

RAW_PATTERNS = [
    # "said" variants
    r"\bI said\b",
    r"\bhe said\b",
    r"\bshe said\b",
    r"\bwe said\b",
    r"\bthey said\b",
    # "says" variants
    r"\bI says\b",
    r"\bhe says\b",
    r"\bshe says\b",
    r"\bwe says\b",
    r"\bthey says\b",
    # Discourse / rhetorical tags
    r",\s*see\?",
    r",\s*okay\?",
]
PATTERNS = [re.compile(p, re.IGNORECASE) for p in RAW_PATTERNS]

# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------
def contains_trigger(text: str) -> bool:
    return any(pattern.search(text) for pattern in PATTERNS)

def process_file(path: Path) -> int:
    modified_count = 0
    rows = []

    with path.open(newline="", encoding="utf-8") as infile:
        reader = csv.reader(infile)
        for row in reader:
            if len(row) >= 3 and contains_trigger(row[2]):
                row[0] = REPLACEMENT_SPEAKER
                modified_count += 1
            rows.append(row)

    # Write to a temp file alongside the original, then replace atomically
    tmp = path.with_suffix(".tmp")
    try:
        with tmp.open("w", newline="", encoding="utf-8") as outfile:
            writer = csv.writer(outfile, quoting=csv.QUOTE_MINIMAL)
            writer.writerows(rows)
        shutil.move(str(tmp), str(path))
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    return modified_count

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replace speaker labels on rows with reported-speech triggers (in place)."
    )
    parser.add_argument("file", help="Path to the CSV file to process")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.is_file():
        sys.exit(f"[ERROR] File not found: {path}")

    modified = process_file(path)
    print(f"Done. {path.name}: {modified} row(s) modified (edited in place).")

if __name__ == "__main__":
    main()