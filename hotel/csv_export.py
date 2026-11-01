import csv

from .models import ExportError

GUEST_COLUMNS = ["channel_id", "sequence_id", "node_id", "room_no"]
MOVE_COLUMNS = ["channel_id", "sequence_id", "old_node_id", "new_node_id", "room_no"]
EXPERIMENT_COLUMNS = ["experiment", "salt", "method", "K", "N", "V", "metric", "value", "unit"]


def _write(path, columns, rows) -> int:
    rows = list(rows)                     
    try:
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)
    except OSError as e:
        raise ExportError(f"เขียนไฟล์ {path!r} ไม่ได้: {e}") from e
    return len(rows)


def export_guests(system, path) -> int:
    return _write(path, GUEST_COLUMNS, system.iter_guests())


def export_moves(report, path) -> int:
    rows = [(m.c, m.s, m.old_node, m.new_node, m.room_no) for m in report.moves]
    return _write(path, MOVE_COLUMNS, rows)


def export_experiment(rows, path) -> int:
    out = []
    for i, row in enumerate(rows):
        missing = [c for c in EXPERIMENT_COLUMNS if c not in row]
        if missing:
            raise ExportError(f"แถวที่ {i} ขาดคอลัมน์ {missing}")
        out.append([row[c] for c in EXPERIMENT_COLUMNS])
    return _write(path, EXPERIMENT_COLUMNS, out)
