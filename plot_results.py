"""วาดกราฟ (ก) (ข) (ค) จาก experiments/results/summary.csv

วิธีรัน (หลังรัน experiments.run_experiments แล้ว):
    python -m experiments.plot_results
    python -m experiments.plot_results --lang en     # ถ้าเครื่องไม่มีฟอนต์ไทย

ทุกกราฟ: มีชื่อแกน หน่วย พารามิเตอร์ และแสดงความแปรปรวนของ 3 รอบ
(เส้น = ค่าเฉลี่ย, แท่ง = ช่วงต่ำสุด-สูงสุด)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # วาดลงไฟล์ ไม่ต้องมีหน้าต่าง
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter  # noqa: E402

plt.rcParams["axes.unicode_minus"] = False  # ฟอนต์ไทยบางตัวไม่มีเครื่องหมายลบ Unicode

from experiments.results_io import read_summary, rebuild_summary  # noqa: E402

DEFAULT_RESULTS = Path(__file__).resolve().parent / "results"
THAI_FONTS = [
    "Leelawadee UI", "Tahoma", "Noto Sans Thai", "TH Sarabun New", "Sarabun",
    "Angsana New", "Cordia New", "Norasi", "Garuda", "Loma", "Kinnari", "Tlwg Typist",
]

TEXT = {
    "th": {
        "rounds": "รอบ", "bars": "เส้น = ค่าเฉลี่ย, แท่ง = ต่ำสุด–สูงสุด",
        "a_suptitle": "การทดลอง A: เวลาเทียบจำนวนแขก K",
        "a_left": "เวลารวมของแต่ละขั้นตอน", "a_right": "เวลาค้นหาต่อครั้ง",
        "a_x": "จำนวนแขก K (คน)", "a_y_left": "เวลา (วินาที)", "a_y_right": "เวลาต่อครั้ง (ไมโครวินาที)",
        "place": "จัดแขก (ทั้งชุด)", "build": "สร้างวงแหวน", "sort": "เรียงรายการห้อง",
        "by_guest": "ค้นด้วยรหัสแขก", "by_room": "ค้นด้วยที่อยู่ห้อง", "compute": "คำนวณอาคารจากวงแหวน",
        "b_suptitle": "การทดลอง B: อัตราการย้ายเมื่อเพิ่ม/ลบ 1 อาคาร",
        "b_add": "เพิ่ม 1 อาคาร", "b_remove": "ลบ 1 อาคาร",
        "b_x": "จำนวนอาคารก่อนเปลี่ยน N (หลัง)", "b_y": "อัตราการย้าย = แขกที่ย้าย / K",
        "ring": "Consistent Hashing", "modn": "hash mod N", "expected": "ค่าคาดหวัง Consistent Hashing",
        "c_suptitle": "การทดลอง C: ผลของจำนวน virtual node (V)",
        "c_left": "ความสมดุลของโหลด", "c_right": "หน่วยความจำที่ Python ติดตาม",
        "c_x": "virtual node ต่ออาคาร V", "c_y_left": "CV = SD / ค่าเฉลี่ย (ยิ่งต่ำยิ่งสมดุล)",
        "c_y_right": "หน่วยความจำ (MiB)", "peak": "peak", "current": "current",
    },
    "en": {
        "rounds": "rounds", "bars": "line = mean, bars = min-max",
        "a_suptitle": "Experiment A: time vs number of guests K",
        "a_left": "Total time per stage", "a_right": "Time per lookup",
        "a_x": "Guests K", "a_y_left": "Time (s)", "a_y_right": "Time per call (us)",
        "place": "place guests (whole batch)", "build": "build ring", "sort": "sort room list",
        "by_guest": "search by guest id", "by_room": "search by room address", "compute": "compute node from ring",
        "b_suptitle": "Experiment B: migration rate when adding/removing 1 building",
        "b_add": "Add 1 building", "b_remove": "Remove 1 building",
        "b_x": "Buildings before change N", "b_y": "Migration rate = moved guests / K",
        "ring": "Consistent Hashing", "modn": "hash mod N", "expected": "Consistent Hashing expected",
        "c_suptitle": "Experiment C: effect of virtual nodes (V)",
        "c_left": "Load balance", "c_right": "Python-tracked memory",
        "c_x": "Virtual nodes per building V", "c_y_left": "CV = SD / mean (lower = more balanced)",
        "c_y_right": "Memory (MiB)", "peak": "peak", "current": "current",
    },
}


def has_thai_font() -> bool:
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in THAI_FONTS:
        if name in available:
            plt.rcParams["font.family"] = name
            return True
    return False


def _series(summary, experiment, method, metric, x_key, **fixed):
    pts = []
    for r in summary:
        if (r["experiment"], r["method"], r["metric"]) != (experiment, method, metric):
            continue
        if any(r[k] != val for k, val in fixed.items()):
            continue
        pts.append((r[x_key], r["mean"], r["min"], r["max"], r["rounds"]))
    pts.sort()
    return pts


def _errorbar(ax, pts, label, scale=1.0, **kwargs):
    if not pts:
        return
    xs = [p[0] for p in pts]
    mean = [p[1] * scale for p in pts]
    lower = [max(0.0, (p[1] - p[2]) * scale) for p in pts]
    upper = [max(0.0, (p[3] - p[1]) * scale) for p in pts]
    ax.errorbar(xs, mean, yerr=[lower, upper], marker="o", capsize=3, label=label, **kwargs)


def _first(summary, experiment):
    return next((r for r in summary if r["experiment"] == experiment), None)


def _save(fig, path: Path) -> Path:
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_a(summary, out_dir: Path, L: dict):
    ref = _first(summary, "A")
    if ref is None:
        return None
    fig, (left, right) = plt.subplots(1, 2, figsize=(12, 4.8))
    for metric, key in (("place_guests_s", "place"), ("build_ring_s", "build"), ("sort_rooms_s", "sort")):
        _errorbar(left, _series(summary, "A", "ring", metric, "K"), L[key])
    for metric, key in (("search_by_guest_per_call_s", "by_guest"), ("search_by_room_per_call_s", "by_room"),
                        ("compute_node_per_call_s", "compute")):
        _errorbar(right, _series(summary, "A", "ring", metric, "K"), L[key], scale=1e6)
    k_values = sorted({r["K"] for r in summary if r["experiment"] == "A"})
    for ax, title, ylabel in ((left, L["a_left"], L["a_y_left"]), (right, L["a_right"], L["a_y_right"])):
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xticks(k_values)
        ax.set_xticklabels([f"{k:,}" for k in k_values])
        ax.xaxis.set_minor_formatter(NullFormatter())
        # ตัวเลขธรรมดาแทนรูป 10^n (ฟอนต์ไทยบางตัวแสดงเครื่องหมายลบของเลขยกกำลังไม่ได้)
        ax.yaxis.set_major_locator(LogLocator(base=10, subs=(1.0, 2.0, 5.0)))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:g}"))
        ax.yaxis.set_minor_formatter(NullFormatter())
        ax.set_xlabel(L["a_x"])
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(True, which="both", alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle(f"{L['a_suptitle']}\nN={ref['N']}, V={ref['V']} | {ref['rounds']} {L['rounds']} ({L['bars']})")
    fig.tight_layout()
    return _save(fig, out_dir / "fig_a_time_vs_K.png")


def plot_b(summary, out_dir: Path, L: dict):
    ref = _first(summary, "B")
    if ref is None:
        return None
    n_values = sorted({r["N"] for r in summary if r["experiment"] == "B"})
    fig, (left, right) = plt.subplots(1, 2, figsize=(12, 4.8))
    panels = ((left, "add", L["b_add"], lambda n: 1 / (n + 1)), (right, "remove", L["b_remove"], lambda n: 1 / n))
    for ax, action, title, expected in panels:
        for method, style in (("ring", "-"), ("modn", "-")):
            _errorbar(ax, _series(summary, "B", method, f"{action}_move_rate", "N"), L[method], linestyle=style)
        usable = [n for n in n_values if not (action == "remove" and n < 2)]
        ax.plot(usable, [expected(n) for n in usable], "k--", marker="x", label=L["expected"])
        ax.set_xticks(n_values)
        ax.set_ylim(0, 1.05)
        ax.set_xlabel(L["b_x"])
        ax.set_ylabel(L["b_y"])
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle(f"{L['b_suptitle']}\nK={ref['K']:,}, V={ref['V']} | {ref['rounds']} {L['rounds']} ({L['bars']})")
    fig.tight_layout()
    return _save(fig, out_dir / "fig_b_move_rate_vs_N.png")


def plot_c(summary, out_dir: Path, L: dict):
    ref = _first(summary, "C")
    if ref is None:
        return None
    v_values = sorted({r["V"] for r in summary if r["experiment"] == "C"})
    fig, (left, right) = plt.subplots(1, 2, figsize=(12, 4.8))
    _errorbar(left, _series(summary, "C", "ring", "cv", "V"), "CV")
    _errorbar(right, _series(summary, "C", "ring", "mem_peak_mib", "V"), L["peak"])
    _errorbar(right, _series(summary, "C", "ring", "mem_current_mib", "V"), L["current"], linestyle="--")
    for ax, title, ylabel in ((left, L["c_left"], L["c_y_left"]), (right, L["c_right"], L["c_y_right"])):
        ax.set_xscale("log", base=2)
        ax.set_xticks(v_values)
        ax.set_xticklabels([str(v) for v in v_values])
        ax.set_xlabel(L["c_x"])
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(True, which="both", alpha=0.3)
    right.legend(fontsize=8)
    fig.suptitle(f"{L['c_suptitle']}\nN={ref['N']}, K={ref['K']:,} | {ref['rounds']} {L['rounds']} ({L['bars']})")
    fig.tight_layout()
    return _save(fig, out_dir / "fig_c_V_effect.png")


def plot_all(results_dir=DEFAULT_RESULTS, lang: str = "auto") -> list[Path]:
    results_dir = Path(results_dir)
    summary_path = results_dir / "summary.csv"
    if summary_path.exists():
        summary = read_summary(summary_path)
    else:
        summary = rebuild_summary(results_dir)
        summary = read_summary(summary_path) if summary_path.exists() else []
    if not summary:
        raise SystemExit(f"ไม่พบผลทดลองใน {results_dir} ให้รัน python -m experiments.run_experiments ก่อน")

    thai = has_thai_font()
    if lang == "th":
        thai = True
    elif lang == "en":
        thai = False
    elif not thai:
        print("ไม่พบฟอนต์ไทยในเครื่อง -> ใช้ป้ายภาษาอังกฤษ (เพิ่ม --lang th ถ้าติดตั้งฟอนต์แล้ว)")
    L = TEXT["th" if thai else "en"]

    saved = []
    for plot in (plot_a, plot_b, plot_c):
        path = plot(summary, results_dir, L)
        if path is not None:
            saved.append(path)
            print(f"บันทึกกราฟ: {path}")
    return saved


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="วาดกราฟผลการทดลอง")
    parser.add_argument("--results", default=str(DEFAULT_RESULTS), help="โฟลเดอร์ที่มี summary.csv")
    parser.add_argument("--lang", choices=("auto", "th", "en"), default="auto")
    args = parser.parse_args(argv)
    plot_all(args.results, args.lang)
    return 0


if __name__ == "__main__":
    sys.exit(main())
