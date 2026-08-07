import argparse
import csv
import re
import sys
import tempfile
import shutil
from pathlib import Path

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------
TWO_PARAGRAPH_THRESHOLD = 800
LEFT_FRAG_WORDS = 3
RIGHT_FRAG_WORDS = 3

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_TERMINAL_RE = re.compile(r"[.?!]\s*$")
_HEADER_LABELS = {"speaker", "speaker name", "name", "start time", "start", "text"}

def ends_sentence(text: str) -> bool:
    return bool(_TERMINAL_RE.search(text.rstrip()))

def strip_terminal(text: str) -> str:
    return _TERMINAL_RE.sub("", text).rstrip()

def wc(text: str) -> int:
    return len(text.split())

def is_left_frag(accumulated: str) -> bool:
    t = accumulated.strip()
    if not ends_sentence(t):
        return True
    return wc(t) <= LEFT_FRAG_WORDS

def is_right_frag(seg: str) -> bool:
    t = seg.strip()
    if not ends_sentence(t):
        return True
    return wc(t) <= RIGHT_FRAG_WORDS

def need_ellipsis(left: str, right: str, prev_right_was_frag: bool) -> bool:
    if is_left_frag(left): return True
    if is_right_frag(right): return True
    if prev_right_was_frag: return True
    return False

def join_segments(left: str, right: str, prev_right_was_frag: bool) -> str:
    left = left.rstrip()
    right = right.strip()
    if not right: return left
    if not left: return right
    if need_ellipsis(left, right, prev_right_was_frag):
        clean_left = strip_terminal(left)
        cont = right[0].lower() + right[1:]
        return f"{clean_left}… {cont}"
    return f"{left} {right}"

# ---------------------------------------------------------------------------
# CSV sniffing / reading
# ---------------------------------------------------------------------------
def sniff_delimiter(path: Path) -> str:
    with path.open(encoding="utf-8-sig") as fh:
        first = fh.readline()
    if "\t" in first and "," not in first:
        return "\t"
    return ","

def is_header_row(row: list[str]) -> bool:
    if not row: return False
    return row[0].strip().lower() in _HEADER_LABELS

def read_rows_with_header(path: Path):
    """Returns (delimiter, header_row, data_rows)"""
    delim = sniff_delimiter(path)
    header = None
    data = []

    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh, delimiter=delim)
        for i, row in enumerate(reader):
            if not row: continue
            if i == 0 and is_header_row(row):
                header = row
                continue
            while len(row) < 4:
                row.append("")
            data.append(row)

    return delim, header, data

# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------
def process_file(path: Path):
    delim, header, rows = read_rows_with_header(path)
    if not rows:
        print(f"  [skip] {path.name} — empty or unreadable")
        return 0

    out_rows = []
    if header:
        out_rows.append(header)

    run_speaker = ""
    run_segments = []

    def emit_run():
        if not run_segments:
            return

        accumulated_text = run_segments[0][2].strip()
        current_start_ts = run_segments[0][1]
        current_end_ts = run_segments[0][3]
        prev_right_frag = False

        for i in range(1, len(run_segments)):
            seg_text = run_segments[i][2].strip()
            seg_start = run_segments[i][1]
            seg_end = run_segments[i][3]

            if (len(accumulated_text) >= TWO_PARAGRAPH_THRESHOLD
                    and ends_sentence(accumulated_text)
                    and not is_left_frag(accumulated_text)):
                out_rows.append([run_speaker, current_start_ts, accumulated_text, current_end_ts])
                accumulated_text = seg_text
                current_start_ts = seg_start
                current_end_ts = seg_end
                prev_right_frag = False
            else:
                frag_before = prev_right_frag
                prev_right_frag = is_right_frag(seg_text)
                accumulated_text = join_segments(accumulated_text, seg_text, frag_before)
                current_end_ts = seg_end

        out_rows.append([run_speaker, current_start_ts, accumulated_text, current_end_ts])

    for row in rows:
        speaker = row[0].strip()
        if speaker == run_speaker:
            run_segments.append(row)
        else:
            emit_run()
            run_speaker = speaker
            run_segments = [row]

    emit_run()

    # Write to a temp file alongside the original, then replace atomically
    tmp = path.with_suffix(".tmp")
    try:
        with tmp.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh, delimiter=delim)
            writer.writerows(out_rows)
        shutil.move(str(tmp), str(path))
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    return len(out_rows) - (1 if header else 0)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Consolidate consecutive same-speaker rows in a transcript CSV (in place)."
    )
    parser.add_argument("file", help="Path to the CSV file to process")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.is_file():
        sys.exit(f"[ERROR] File not found: {path}")

    n_out = process_file(path)
    print(f"Done. {path.name} consolidated into {n_out} dialogue rows (edited in place).")

if __name__ == "__main__":
    main()