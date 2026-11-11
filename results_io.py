"""อ่าน/เขียน CSV ผลการทดลอง และสรุปผลข้าม 3 รอบ (salt)

ไฟล์นี้ไม่ import แพ็กเกจ hotel เพื่อให้ plot_results.py ใช้ได้โดยไม่ต้องสร้างระบบโรงแรม
"""
from __future__ import annotations

import csv
import statistics
from pathlib import Path

# คอลัมน์ตามข้อตกลงใน README หัวข้อ 4 (รูปแบบ CSV)
RESULT_COLUMNS = ["experiment", "salt", "method", "K", "N", "V", "metric", "value", "unit"]
SUMMARY_COLUMNS = [
    "experiment", "method", "K", "N", "V", "metric", "unit",
    "rounds", "median", "mean", "min", "max",
]
EXPERIMENT_NAMES = ("A", "B", "C")


def unit_of(metric: str) -> str:
    """หน่วยของตัวชี้วัด ตามชื่อ metric"""
    if metric.endswith("_mib"):
        return "MiB"
    if metric.endswith("_s"):
        return "s"
    if metric.endswith("_rate") or metric == "cv":
        return "ratio"
    return "guests"  # moved, load_*, expected_*


def make_row(experiment, salt, method, k, n, v, metric, value, unit=None) -> dict:
    return {
        "experiment": experiment,
        "salt": salt,
        "method": method,
        "K": k,
        "N": n,
        "V": v,
        "metric": metric,
        "value": value,
        "unit": unit if unit is not None else unit_of(metric),
    }


def write_rows(path, rows, columns=RESULT_COLUMNS) -> int:
    """เขียน CSV แบบ UTF-8 (เปิดด้วย newline="") คืนจำนวนแถวที่เขียน"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def read_rows(path) -> list[dict]:
    """อ่านไฟล์ผลดิบ (experiment_*.csv) แล้วแปลงชนิดข้อมูลตัวเลข"""
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            for key in ("K", "N", "V"):
                r[key] = int(r[key])
            r["value"] = float(r["value"]) if r["value"] != "" else None
            rows.append(r)
    return rows


def read_summary(path) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            for key in ("K", "N", "V", "rounds"):
                r[key] = int(r[key])
            for key in ("median", "mean", "min", "max"):
                r[key] = float(r[key])
            rows.append(r)
    return rows


def summarize(rows: list[dict]) -> list[dict]:
    """รวมผลหลายรอบ (หลาย salt) ของค่าพารามิเตอร์ชุดเดียวกัน -> มัธยฐาน/เฉลี่ย/ต่ำสุด/สูงสุด"""
    groups: dict[tuple, list[float]] = {}
    for r in rows:
        if r["value"] is None or r["value"] == "":
            continue
        key = (r["experiment"], r["method"], r["K"], r["N"], r["V"], r["metric"], r["unit"])
        groups.setdefault(key, []).append(float(r["value"]))
    out = []
    for (experiment, method, k, n, v, metric, unit), values in groups.items():
        out.append({
            "experiment": experiment, "method": method, "K": k, "N": n, "V": v,
            "metric": metric, "unit": unit, "rounds": len(values),
            "median": statistics.median(values), "mean": statistics.fmean(values),
            "min": min(values), "max": max(values),
        })
    return out


def rebuild_summary(out_dir) -> list[dict]:
    """อ่าน experiment_A/B/C.csv ที่มีอยู่ในโฟลเดอร์ แล้วเขียน summary.csv ใหม่ (รวมทุกชุดที่มี)"""
    out_dir = Path(out_dir)
    rows: list[dict] = []
    for name in EXPERIMENT_NAMES:
        path = out_dir / f"experiment_{name}.csv"
        if path.exists():
            rows.extend(read_rows(path))
    summary = summarize(rows)
    write_rows(out_dir / "summary.csv", summary, SUMMARY_COLUMNS)
    return summary
