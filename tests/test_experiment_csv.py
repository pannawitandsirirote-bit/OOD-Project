"""ตรวจ CSV ผลการทดลอง (experiments/run_experiments.py + results_io.py)

รันชุดทดลองขนาดเล็ก (--quick) 3 salt แล้วตรวจโครงสร้าง ความครบ และความสอดคล้องของตัวเลข
ผลของชุดเต็มสำหรับรายงานให้รันด้วย: python -m experiments.run_experiments --exp all --salts 0 1 2

รัน: python -m unittest tests.test_experiment_csv -v
"""
import csv
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from experiments import run_experiments as exp
from experiments.results_io import (
    RESULT_COLUMNS,
    SUMMARY_COLUMNS,
    read_rows,
    read_summary,
    summarize,
)

SALTS = ("0", "1", "2")


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


class TestExperimentOutputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name)
        cls.cfg = exp.QUICK
        exp.run_all(("A", "B", "C"), SALTS, cls.out, quick=True, log=lambda *_: None)
        cls.rows = {name: read_rows(cls.out / f"experiment_{name}.csv") for name in "ABC"}

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    # ---- โครงสร้างไฟล์
    def test_files_exist_and_header_matches_agreed_format(self):
        for name in "ABC":
            header, rows = read_csv(self.out / f"experiment_{name}.csv")
            self.assertEqual(header, RESULT_COLUMNS)
            self.assertGreater(len(rows), 0)
        header, rows = read_csv(self.out / "summary.csv")
        self.assertEqual(header, SUMMARY_COLUMNS)
        self.assertTrue((self.out / "run_info.txt").exists())

    def test_no_empty_cells_and_numeric_values(self):
        for name in "ABC":
            _, rows = read_csv(self.out / f"experiment_{name}.csv")
            for r in rows:
                for col in RESULT_COLUMNS:
                    self.assertNotEqual(r[col], "", msg=f"{name}: {r}")
                float(r["value"])
                self.assertIn(r["unit"], {"s", "MiB", "ratio", "guests"})
                self.assertEqual(r["experiment"], name)

    def test_every_salt_present_for_every_parameter_set(self):
        for name in "ABC":
            per_key = defaultdict(set)
            for r in self.rows[name]:
                per_key[(r["method"], r["K"], r["N"], r["V"], r["metric"])].add(r["salt"])
            for key, salts in per_key.items():
                self.assertEqual(salts, set(SALTS), msg=f"{name} {key}")

    # ---- ความครบของพารามิเตอร์ตามหัวข้อ 7.1
    def test_experiment_a_covers_all_k_with_time_and_memory(self):
        rows = self.rows["A"]
        self.assertEqual({r["K"] for r in rows}, set(self.cfg["a_k"]))
        self.assertEqual({(r["N"], r["V"]) for r in rows}, {(self.cfg["a_n"], self.cfg["a_v"])})
        metrics = {r["metric"] for r in rows}
        for needed in ("build_ring_s", "place_guests_s", "search_by_guest_per_call_s",
                       "search_by_room_per_call_s", "sort_rooms_s", "mem_current_mib", "mem_peak_mib"):
            self.assertIn(needed, metrics)

    def test_experiment_b_covers_n_and_both_methods(self):
        rows = self.rows["B"]
        self.assertEqual({r["N"] for r in rows}, set(self.cfg["b_n"]))
        self.assertEqual({r["method"] for r in rows}, {"ring", "modn"})
        for method in ("ring", "modn"):
            metrics = {r["metric"] for r in rows if r["method"] == method}
            for needed in ("add_moved", "add_move_rate", "add_time_s",
                           "remove_moved", "remove_move_rate", "remove_time_s"):
                self.assertIn(needed, metrics, msg=method)

    def test_experiment_c_covers_v_and_loads_sum_to_k(self):
        rows = self.rows["C"]
        self.assertEqual({r["V"] for r in rows}, set(self.cfg["c_v"]))
        k, n = self.cfg["c_k"], self.cfg["c_n"]
        for v in self.cfg["c_v"]:
            for salt in SALTS:
                loads = [r["value"] for r in rows
                         if r["V"] == v and r["salt"] == salt and r["metric"].startswith("load_node_")]
                self.assertEqual(len(loads), n, msg="ต้องรายงานทุกอาคาร (รวมที่มี 0 คน)")
                self.assertEqual(sum(loads), k)
        self.assertIn("cv", {r["metric"] for r in rows})

    # ---- ความสอดคล้องของตัวเลข
    def test_move_rate_equals_moved_over_k(self):
        for name in ("B", "C"):
            by_key = defaultdict(dict)
            for r in self.rows[name]:
                by_key[(r["salt"], r["method"], r["N"], r["V"])][r["metric"]] = r["value"]
            for key, m in by_key.items():
                for action in ("add", "remove"):
                    if f"{action}_moved" in m:
                        k = self.cfg["b_k"] if name == "B" else self.cfg["c_k"]
                        self.assertAlmostEqual(m[f"{action}_move_rate"], m[f"{action}_moved"] / k, places=9, msg=key)

    def test_consistent_hashing_moves_fewer_guests_than_mod_n(self):
        """ผลที่โจทย์คาดหวัง: ring ย้ายน้อยกว่า hash mod N อย่างชัดเจน (เทียบแต่ละ N และ salt)"""
        by_key = defaultdict(dict)
        for r in self.rows["B"]:
            if r["metric"] == "add_moved":
                by_key[(r["salt"], r["N"])][r["method"]] = r["value"]
        for key, m in by_key.items():
            self.assertLess(m["ring"], m["modn"], msg=key)

    def test_memory_and_time_values_are_sane(self):
        for r in self.rows["A"]:
            if r["unit"] in ("s", "MiB"):
                self.assertGreaterEqual(r["value"], 0, msg=r)
        for r in self.rows["A"]:
            if r["metric"] == "mem_peak_mib":
                current = next(x["value"] for x in self.rows["A"]
                               if (x["salt"], x["K"], x["metric"]) == (r["salt"], r["K"], "mem_current_mib"))
                self.assertGreaterEqual(r["value"], current)   # peak ต้องไม่น้อยกว่า current

    def test_summary_matches_raw_rows(self):
        summary = read_summary(self.out / "summary.csv")
        self.assertEqual(len(summary), len(summarize([r for n in "ABC" for r in self.rows[n]])))
        for s in summary:
            self.assertEqual(s["rounds"], len(SALTS))
            eps = 1e-9 * max(1.0, abs(s["max"]))   # เผื่อความคลาดเคลื่อนทศนิยมของค่าเฉลี่ย
            self.assertLessEqual(s["min"], s["median"])
            self.assertLessEqual(s["median"], s["max"])
            self.assertLessEqual(s["min"] - eps, s["mean"])
            self.assertLessEqual(s["mean"], s["max"] + eps)


class TestHelpers(unittest.TestCase):
    def test_split_guests_balanced_and_exact(self):
        for k in (0, 1, 9, 10, 11, 1000, 100_001):
            counts = exp.split_guests(k)
            self.assertEqual(len(counts), exp.N_CHANNELS)
            self.assertEqual(sum(counts), k)
            self.assertLessEqual(max(counts) - min(counts), 1)

    def test_timing_refuses_to_run_under_tracemalloc(self):
        import tracemalloc
        tracemalloc.start()
        try:
            with self.assertRaises(exp.ExperimentCheckError):
                exp.measure_timing("ring", 3, 4, 100, "0")
        finally:
            tracemalloc.stop()

    def test_unit_rules(self):
        from experiments.results_io import unit_of
        self.assertEqual(unit_of("build_ring_s"), "s")
        self.assertEqual(unit_of("mem_peak_mib"), "MiB")
        self.assertEqual(unit_of("add_move_rate"), "ratio")
        self.assertEqual(unit_of("cv"), "ratio")
        self.assertEqual(unit_of("add_moved"), "guests")
        self.assertEqual(unit_of("load_node_3"), "guests")


if __name__ == "__main__":
    unittest.main()
