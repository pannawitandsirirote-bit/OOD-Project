"""การทดลอง A / B / C ตามหัวข้อ 7 ของโจทย์

วิธีรัน (จากโฟลเดอร์โปรเจกต์):
    python -m experiments.run_experiments --exp all --salts 0 1 2
    python -m experiments.run_experiments --exp A --quick      # ชุดเล็ก ใช้ตรวจว่าโค้ดทำงาน (ไม่ใช่ผลสำหรับรายงาน)

หลักการวัด (หัวข้อ 7.2):
  * เวลา       : time.perf_counter() แยกทีละขั้น ไม่รวมเวลา print / เขียนไฟล์
                 ค้นหาวัดเป็นชุด 1,000 ครั้งแล้วหารต่อครั้ง ปิด GC ระหว่างจับเวลา
  * หน่วยความจำ: tracemalloc วัดส่วนที่เพิ่มจากจุดเริ่มเดียวกัน (current / peak เป็น MiB)
                 ทำ "แยกรอบ" จากรอบจับเวลา (tracemalloc ทำให้ช้าลง)
  * รายงานผล   : ผลดิบทุก salt ใน experiment_*.csv ; มัธยฐาน/เฉลี่ย/ต่ำสุด/สูงสุดใน summary.csv
  * เทียบ ring กับ modn: ใช้รหัสแขก รหัสอาคาร และ salt ชุดเดียวกันในรอบเดียวกัน
"""
from __future__ import annotations

import argparse
import contextlib
import gc
import platform
import random
import sys
import tracemalloc
from datetime import datetime
from pathlib import Path
from time import perf_counter

from hotel.hotel_system import HotelSystem

from experiments.results_io import (
    EXPERIMENT_NAMES,
    RESULT_COLUMNS,
    SUMMARY_COLUMNS,
    make_row,
    rebuild_summary,
    unit_of,
    write_rows,
)

N_CHANNELS = 10          # สร้างแขกจาก 10 ช่องทาง จำนวนใกล้เคียงกัน
SEARCH_BATCH = 1000      # ค้นหาเป็นชุด 1,000 ครั้งแล้วหารต่อครั้ง
SEARCH_SEED = 12345      # ชุดรหัสที่ใช้ค้นหาเหมือนกันทุกรอบ ทุกวิธี
MIB = 1024 * 1024
METHODS = ("ring", "modn")
DEFAULT_SALTS = ("0", "1", "2")
DEFAULT_OUT = Path(__file__).resolve().parent / "results"

# พารามิเตอร์ตามตารางหัวข้อ 7.1
FULL = {
    "a_k": (1_000, 10_000, 100_000), "a_n": 10, "a_v": 32,
    "b_n": (5, 10, 20), "b_k": 10_000, "b_v": 32,
    "c_v": (1, 8, 32), "c_n": 10, "c_k": 10_000,
}
# ชุดเล็กสำหรับทดสอบว่าโค้ดทำงาน (ผลไม่ใช้ในรายงาน)
QUICK = {
    "a_k": (200, 1_000, 2_000), "a_n": 10, "a_v": 32,
    "b_n": (5, 10, 20), "b_k": 1_000, "b_v": 32,
    "c_v": (1, 8, 32), "c_n": 10, "c_k": 1_000,
}


class ExperimentCheckError(RuntimeError):
    """ผลที่ได้ขัดกับกติกาของระบบ (เช่น คนย้ายไปอาคารที่ไม่ใช่อาคารใหม่) ต้องแก้โค้ดก่อนเชื่อผลทดลอง"""


# ----------------------------------------------------------------------------
# เครื่องมือช่วย
# ----------------------------------------------------------------------------
def split_guests(k: int, channels: int = N_CHANNELS) -> list[int]:
    """แบ่งแขก k คนให้ช่องทางละใกล้เคียงกัน (ต่างกันไม่เกิน 1)"""
    base, extra = divmod(k, channels)
    return [base + (1 if i < extra else 0) for i in range(channels)]


def guest_ids(counts: list[int]) -> list[tuple[int, int]]:
    return [(c, s) for c, n in enumerate(counts, start=1) for s in range(1, n + 1)]


@contextlib.contextmanager
def _no_gc():
    was_enabled = gc.isenabled()
    gc.collect()
    gc.disable()
    try:
        yield
    finally:
        if was_enabled:
            gc.enable()


def _require_not_tracing() -> None:
    if tracemalloc.is_tracing():
        raise ExperimentCheckError("รอบจับเวลาต้องรันโดยไม่เปิด tracemalloc")


def build_system(method: str, n: int, v: int, counts: list[int], salt: str):
    """สร้างระบบและจัดแขก คืน (system, เวลาสร้างวงแหวน, เวลาจัดแขก)"""
    t0 = perf_counter()
    system = HotelSystem.create(n, v, [0] * len(counts), salt=salt, method=method)
    t1 = perf_counter()
    for c, count in enumerate(counts, start=1):
        if count > 0:
            system.add_guests(c, 1, count)
    t2 = perf_counter()
    return system, t1 - t0, t2 - t1


# ----------------------------------------------------------------------------
# ตัววัด (ใช้ทั้งในชุดทดลองและจากเมนูข้อ 10 / 11)
# ----------------------------------------------------------------------------
def measure_timing(method: str, n: int, v: int, k: int, salt: str) -> dict[str, float]:
    """เวลาของฟังก์ชันหลัก (วินาที) -- ต้องไม่เปิด tracemalloc"""
    _require_not_tracing()
    counts = split_guests(k)
    ids = guest_ids(counts)
    result: dict[str, float] = {}
    with _no_gc():
        system, build_s, place_s = build_system(method, n, v, counts, salt)
        result["build_ring_s"] = build_s
        result["place_guests_s"] = place_s
        if system.guest_count != k:
            raise ExperimentCheckError(f"จัดแขกแล้วได้ {system.guest_count} คน ไม่ใช่ {k}")

        # ชุดรหัสที่ใช้ค้นหา: สุ่มแบบกำหนดค่าเริ่มต้นตายตัว เหมือนกันทุกวิธี/ทุกรอบ
        rng = random.Random(SEARCH_SEED)
        sample = rng.choices(ids, k=SEARCH_BATCH) if ids else []
        if sample:
            # ที่อยู่ห้อง (เตรียมไว้นอกส่วนจับเวลา) ใช้ค้นหาย้อนกลับ
            addresses = [system.find_by_guest(c, s) for c, s in sample]
            if any(a is None for a in addresses):
                raise ExperimentCheckError("find_by_guest ไม่พบแขกที่เพิ่งเพิ่มเข้าระบบ")

            t = perf_counter()
            for c, s in sample:
                system.find_by_guest(c, s)
            result["search_by_guest_per_call_s"] = (perf_counter() - t) / len(sample)

            t = perf_counter()
            for node_id, room_no in addresses:
                system.find_by_room(node_id, room_no)
            result["search_by_room_per_call_s"] = (perf_counter() - t) / len(sample)

            t = perf_counter()
            for c, s in sample:
                system.compute_node(c, s)
            result["compute_node_per_call_s"] = (perf_counter() - t) / len(sample)

        t = perf_counter()
        rooms = system.list_rooms()
        result["sort_rooms_s"] = perf_counter() - t
        if len(rooms) != k:
            raise ExperimentCheckError(f"list_rooms ได้ {len(rooms)} แถว ไม่ใช่ {k}")
    return result


def measure_memory(method: str, n: int, v: int, k: int, salt: str) -> dict[str, float]:
    """หน่วยความจำที่ Python ติดตามด้วย tracemalloc (MiB) ส่วนที่เพิ่มจากจุดเริ่มเดียวกัน

    วัดวงแหวน + ข้อมูลแขก + ดัชนี ไม่ใช่หน่วยความจำของทั้งโปรเซส
    """
    counts = split_guests(k)
    gc.collect()
    tracemalloc.start()
    try:
        baseline, _ = tracemalloc.get_traced_memory()
        tracemalloc.reset_peak()
        system, _, _ = build_system(method, n, v, counts, salt)
        current, peak = tracemalloc.get_traced_memory()
        if system.guest_count != k:
            raise ExperimentCheckError(f"จัดแขกแล้วได้ {system.guest_count} คน ไม่ใช่ {k}")
    finally:
        tracemalloc.stop()
    return {
        "mem_current_mib": (current - baseline) / MIB,
        "mem_peak_mib": (peak - baseline) / MIB,
    }


def _check_report(report, k: int, system, method: str, action: str, node_id: int) -> None:
    if report.moved_count != len(report.moves):
        raise ExperimentCheckError("moved_count ไม่เท่ากับจำนวนรายการย้าย")
    if system.guest_count != k:
        raise ExperimentCheckError(f"หลัง {action} อาคาร แขกเหลือ {system.guest_count} คน ไม่ใช่ {k}")
    if any(m.old_node == m.new_node for m in report.moves):
        raise ExperimentCheckError("พบรายการย้ายที่อาคารเดิมเท่ากับอาคารใหม่")
    if method == "ring":  # กติกาหัวข้อ 4.4 ข้อ 2 ใช้กับ Consistent Hashing เท่านั้น
        if action == "add" and any(m.new_node != node_id for m in report.moves):
            raise ExperimentCheckError("เพิ่มอาคาร: มีแขกย้ายไปอาคารที่ไม่ใช่อาคารใหม่")
        if action == "remove" and any(m.old_node != node_id for m in report.moves):
            raise ExperimentCheckError("ลบอาคาร: มีแขกจากอาคารอื่นย้าย")


def measure_migration(method: str, n: int, v: int, k: int, salt: str) -> dict[str, float]:
    """เพิ่ม 1 อาคาร (รหัส n+1) และลบ 1 อาคาร (รหัส n//2+1) แต่ละกรณีเริ่มจากสถานะเดิมใหม่

    คืนเวลา (วินาที) จำนวนแขกที่ย้าย และอัตราย้าย (ไม่ใส่อัตราเมื่อ K = 0)
    การลบจะข้ามเมื่อ N = 1 เพราะห้ามลบอาคารสุดท้าย
    """
    _require_not_tracing()
    counts = split_guests(k)
    result: dict[str, float] = {}

    system, _, _ = build_system(method, n, v, counts, salt)
    new_id = n + 1
    with _no_gc():
        t = perf_counter()
        report = system.add_node(new_id)
        elapsed = perf_counter() - t
    _check_report(report, k, system, method, "add", new_id)
    result["add_time_s"] = elapsed
    result["add_moved"] = report.moved_count
    if report.rate is not None:
        result["add_move_rate"] = report.rate

    if n >= 2:
        system, _, _ = build_system(method, n, v, counts, salt)
        victim = n // 2 + 1
        with _no_gc():
            t = perf_counter()
            report = system.remove_node(victim)
            elapsed = perf_counter() - t
        _check_report(report, k, system, method, "remove", victim)
        result["remove_time_s"] = elapsed
        result["remove_moved"] = report.moved_count
        if report.rate is not None:
            result["remove_move_rate"] = report.rate
    return result


# ----------------------------------------------------------------------------
# ชุดทดลอง
# ----------------------------------------------------------------------------
def run_a(cfg: dict, salts, log) -> list[dict]:
    """A: เปลี่ยน K  (N, V คงที่) -> เวลาจัดแขก ค้นหา เรียงลำดับ และหน่วยความจำ"""
    rows: list[dict] = []
    n, v = cfg["a_n"], cfg["a_v"]
    for k in cfg["a_k"]:
        for salt in salts:
            log(f"[A] K={k:,} N={n} V={v} salt={salt}")
            measured = {**measure_timing("ring", n, v, k, salt), **measure_memory("ring", n, v, k, salt)}
            for metric, value in measured.items():
                rows.append(make_row("A", salt, "ring", k, n, v, metric, value))
    return rows


def run_b(cfg: dict, salts, log) -> list[dict]:
    """B: เปลี่ยน N  (K, V คงที่) -> เพิ่ม/ลบ 1 อาคาร เทียบ ring กับ hash mod N"""
    rows: list[dict] = []
    k, v = cfg["b_k"], cfg["b_v"]
    for n in cfg["b_n"]:
        for salt in salts:
            for method in METHODS:
                log(f"[B] N={n} K={k:,} V={v} salt={salt} method={method}")
                for metric, value in measure_migration(method, n, v, k, salt).items():
                    rows.append(make_row("B", salt, method, k, n, v, metric, value))
            # ค่าคาดหวังเชิงทฤษฎีของ Consistent Hashing (หัวข้อ 4.4) เก็บไว้เทียบกับค่าที่วัดได้
            rows.append(make_row("B", salt, "ring", k, n, v, "add_expected_moves", k / (n + 1)))
            if n >= 2:
                rows.append(make_row("B", salt, "ring", k, n, v, "remove_expected_moves", k / n))
    return rows


def run_c(cfg: dict, salts, log) -> list[dict]:
    """C: เปลี่ยน V  (N, K คงที่) -> โหลดต่ออาคาร CV หน่วยความจำ และการย้าย"""
    rows: list[dict] = []
    n, k = cfg["c_n"], cfg["c_k"]
    counts = split_guests(k)
    for v in cfg["c_v"]:
        for salt in salts:
            log(f"[C] V={v} N={n} K={k:,} salt={salt}")
            system, _, _ = build_system("ring", n, v, counts, salt)
            stats = system.load_stats()
            for node_id in sorted(stats.per_node):
                rows.append(make_row("C", salt, "ring", k, n, v, f"load_node_{node_id}", stats.per_node[node_id]))
            rows.append(make_row("C", salt, "ring", k, n, v, "load_max", stats.max_load))
            rows.append(make_row("C", salt, "ring", k, n, v, "load_min", stats.min_load))
            rows.append(make_row("C", salt, "ring", k, n, v, "load_mean", stats.mean))
            rows.append(make_row("C", salt, "ring", k, n, v, "load_std", stats.std))
            if stats.cv is not None:
                rows.append(make_row("C", salt, "ring", k, n, v, "cv", stats.cv))
            for metric, value in measure_memory("ring", n, v, k, salt).items():
                rows.append(make_row("C", salt, "ring", k, n, v, metric, value))
            for metric, value in measure_migration("ring", n, v, k, salt).items():
                rows.append(make_row("C", salt, "ring", k, n, v, metric, value))
    return rows


RUNNERS = {"A": run_a, "B": run_b, "C": run_c}


def run_all(experiments=EXPERIMENT_NAMES, salts=DEFAULT_SALTS, out_dir=DEFAULT_OUT,
            quick: bool = False, log=print) -> dict[str, list[dict]]:
    """รันชุดทดลองที่เลือก เขียน experiment_*.csv, summary.csv และ run_info.txt ลง out_dir"""
    cfg = QUICK if quick else FULL
    salts = [str(s) for s in salts]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, list[dict]] = {}
    for name in experiments:
        rows = RUNNERS[name](cfg, salts, log)
        write_rows(out_dir / f"experiment_{name}.csv", rows)
        results[name] = rows
        log(f"[{name}] เขียน {len(rows)} แถว -> {out_dir / f'experiment_{name}.csv'}")
    summary = rebuild_summary(out_dir)
    log(f"summary.csv: {len(summary)} แถว (รวมทุกชุดที่มีในโฟลเดอร์)")
    _write_run_info(out_dir, experiments, salts, cfg, quick)
    return results


def _write_run_info(out_dir: Path, experiments, salts, cfg: dict, quick: bool) -> None:
    lines = [
        f"วันเวลา        : {datetime.now().isoformat(timespec='seconds')}",
        f"โหมด           : {'QUICK (ไม่ใช่ผลสำหรับรายงาน)' if quick else 'FULL'}",
        f"ชุดที่รันล่าสุด : {', '.join(experiments)}",
        f"salt           : {', '.join(salts)}  (ใช้ salt เดียวกันกับทั้ง ring และ modn ในรอบเดียวกัน)",
        f"Python         : {platform.python_version()} ({platform.python_implementation()})",
        f"เครื่อง         : {platform.platform()} / {platform.machine()}",
        f"ช่องทาง        : {N_CHANNELS} ช่องทาง จำนวนแขกใกล้เคียงกัน",
        f"ค้นหา          : ชุดละ {SEARCH_BATCH} ครั้ง แล้วหารต่อครั้ง (seed {SEARCH_SEED})",
        "เวลา           : time.perf_counter(), ปิด GC ระหว่างจับเวลา",
        "หน่วยความจำ    : tracemalloc ส่วนที่เพิ่มจากจุดเริ่มเดียวกัน (MiB) ไม่ใช่ของทั้งโปรเซส วัดแยกรอบจากการจับเวลา",
        f"พารามิเตอร์     : {cfg}",
        f"คอลัมน์ผลดิบ    : {', '.join(RESULT_COLUMNS)}",
        f"คอลัมน์สรุป     : {', '.join(SUMMARY_COLUMNS)}",
    ]
    (out_dir / "run_info.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="รันการทดลอง A/B/C ของ Distributed Hilbert's Hotel")
    parser.add_argument("--exp", nargs="+", default=["all"], help="A B C หรือ all (ค่าเริ่มต้น all)")
    parser.add_argument("--salts", nargs="+", default=list(DEFAULT_SALTS), help="salt ของแต่ละรอบ (ค่าเริ่มต้น 0 1 2)")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="โฟลเดอร์ผลลัพธ์")
    parser.add_argument("--quick", action="store_true", help="ชุดเล็ก ใช้ตรวจว่าโค้ดทำงาน")
    args = parser.parse_args(argv)

    chosen = [e.upper() for e in args.exp]
    if "ALL" in chosen:
        chosen = list(EXPERIMENT_NAMES)
    unknown = [e for e in chosen if e not in RUNNERS]
    if unknown:
        parser.error(f"ไม่รู้จักชุดทดลอง: {', '.join(unknown)} (เลือกจาก A B C all)")

    run_all(chosen, args.salts, args.out, args.quick)
    return 0


if __name__ == "__main__":
    sys.exit(main())
