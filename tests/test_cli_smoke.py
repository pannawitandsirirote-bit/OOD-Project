"""Smoke test ของเมนูข้อความ (cli/menu.py)

ป้อนคำสั่งแบบสคริปต์เข้าเมนูแล้วตรวจว่า
  * ทุกเมนูทำงานได้และไม่มี "ข้อผิดพลาดที่ไม่คาดคิด" (= บั๊ก)
  * กรณีขอบ (หัวข้อ 4.5) และ input ผิดรูปแบบ ถูกปฏิเสธอย่างสุภาพ แล้วโปรแกรมไม่หยุดทำงาน
  * CSV ที่ส่งออกมีจำนวนแถวเท่ากับจำนวนแขกในระบบ

รัน: python -m unittest tests.test_cli_smoke -v
"""
import csv
import tempfile
import unittest
from pathlib import Path

from cli.menu import Menu
from experiments.results_io import RESULT_COLUMNS

CRASH_MARK = "ไม่คาดคิด"
INIT_10 = ["1", "3", "4", "2", "5", ""]          # N=3, V=4, 2 ช่องทาง ช่องละ 5 คน -> K = 10, ไม่ใช้ salt


class ScriptedIO:
    """แทน input()/print() : ป้อนคำตอบตามลำดับ, หมดแล้วให้ EOFError (เมนูต้องจบอย่างสุภาพ)"""

    def __init__(self, lines):
        self.lines = list(lines)
        self.out = []

    def input(self, prompt=""):
        self.out.append(prompt)
        if not self.lines:
            raise EOFError
        return self.lines.pop(0)

    def print(self, *args, **kwargs):
        self.out.append(" ".join(str(a) for a in args))

    @property
    def text(self):
        return "\n".join(self.out)


class MenuTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data_dir = Path(self._tmp.name)

    def run_menu(self, lines):
        io = ScriptedIO(lines)
        menu = Menu(input_fn=io.input, print_fn=io.print, data_dir=self.data_dir)
        menu.run()  # ต้องคืนค่าปกติ ไม่ raise
        self.assertNotIn(CRASH_MARK, io.text, msg=io.text)
        return io.text, menu


class TestHappyPath(MenuTestCase):
    def test_all_main_functions_run(self):
        text, menu = self.run_menu(
            INIT_10
            + ["8", "0"]                    # รายการห้อง (ทั้งหมด)
            + ["6", "1", "1"]               # ค้นด้วยรหัสแขก เจอ
            + ["6", "9", "9"]               # ค้นด้วยรหัสแขก ไม่เจอ
            + ["7", "1", "1"]               # ค้นด้วยที่อยู่ห้อง (ผลเจอหรือไม่ก็ได้ ต้องไม่ล้ม)
            + ["9"]                         # รายงานโหลด
            + ["4", ""]                     # เพิ่มอาคาร (รหัสปริยาย)
            + ["5", "1"]                    # ลบอาคาร 1
            + ["12", "1", ""]               # ส่งออก guests.csv
            + ["12", "2", ""]               # ส่งออก moves.csv
            + ["0"]
        )
        self.assertIn("K = 10", text)
        self.assertIn("ไม่พบแขก (9, 9)", text)
        self.assertIn("CV =", text)
        self.assertIn("จำนวนแขกที่ย้าย =", text)
        self.assertIn("ออกจากโปรแกรม", text)

    def test_guests_csv_rows_equal_guest_count(self):
        self.run_menu(INIT_10 + ["4", ""] + ["12", "1", ""] + ["0"])
        with open(self.data_dir / "guests.csv", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 10)
        self.assertEqual(list(rows[0].keys()), ["channel_id", "sequence_id", "node_id", "room_no"])

    def test_moves_csv_rows_equal_reported_moves(self):
        text, _ = self.run_menu(INIT_10 + ["4", ""] + ["12", "2", ""] + ["0"])
        with open(self.data_dir / "moves.csv", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        reported = int(text.split("จำนวนแขกที่ย้าย =")[1].split()[0])
        self.assertEqual(len(rows), reported)

    def test_add_and_remove_guests(self):
        text, _ = self.run_menu(
            INIT_10
            + ["2", "1", "3", "1"]          # เพิ่มรายคนช่องทางใหม่ (3, 1)
            + ["2", "2", "1", "6", "4"]     # เพิ่มกลุ่ม c=1, s=6..9
            + ["2", "2", "2", "6", "0"]     # กลุ่มจำนวน 0 -> ไม่เปลี่ยน
            + ["3", "3", "1"]               # นำ (3, 1) ออก
            + ["9", "0"]
        )
        self.assertIn("ไม่เปลี่ยนข้อมูล", text)
        self.assertIn("แขกทั้งหมด K = 14", text)  # 10 + 1 + 4 - 1

    def test_measure_and_compare_and_export_experiment_rows(self):
        text, _ = self.run_menu(
            ["10", "300", "3", "4", "7"]    # K=300 N=3 V=4 salt=7
            + ["12", "3", ""]
            + ["11", "300", "3", "4", "7"]
            + ["0"]
        )
        self.assertIn("สร้างวงแหวน", text)
        self.assertIn("MiB", text)
        self.assertIn("ring", text)
        self.assertIn("modn", text)
        path = self.data_dir / "experiment_menu.csv"
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(reader.fieldnames, RESULT_COLUMNS)
        self.assertGreater(len(rows), 0)
        self.assertTrue(all(r["value"] != "" and r["unit"] != "" for r in rows))


class TestRobustness(MenuTestCase):
    def test_commands_before_init_are_refused(self):
        text, _ = self.run_menu(["2", "3", "4", "5", "6", "7", "8", "9", "12", "1", "0"])
        self.assertGreaterEqual(text.count("ยังไม่ได้เริ่มระบบ"), 8)

    def test_unknown_and_malformed_menu_choices(self):
        text, _ = self.run_menu(["abc", "", "99", "-1", "1.5", "0"])
        self.assertEqual(text.count("ไม่มีเมนู"), 5)

    def test_bad_numbers_do_not_stop_program(self):
        text, _ = self.run_menu(
            ["1", "x"]                                  # N ไม่ใช่ตัวเลข
            + ["1", "0"]                                # N = 0
            + ["1", "3", "4", "2", "5 -2", ""]          # จำนวนแขกติดลบ
            + ["1", "3", "4", "2", "1 2 3", ""]         # จำนวนค่าไม่ตรงช่องทาง
            + ["1", "3", "4", "2", "5", ""]             # ถูกต้อง
            + ["2", "1", "x"]                           # s ไม่ใช่ตัวเลข
            + ["2", "2", "1", "11", "-3"]               # count ติดลบ
            + ["2", "2", "1", "11", "99999999"]         # count ใหญ่เกิน
            + ["2", "7"]                                # โหมดเพิ่มแขกไม่มีอยู่จริง
            + ["6", "0", "1"]                           # c = 0
            + ["9", "0"]
        )
        self.assertGreaterEqual(text.count("ข้อมูลไม่ถูกต้อง"), 9)
        self.assertIn("แขกทั้งหมด K = 10", text)       # ระบบที่ถูกต้องยังอยู่ ข้อมูลไม่เปลี่ยน

    def test_edge_cases_section_4_5_rejected_politely(self):
        text, _ = self.run_menu(
            INIT_10
            + ["4", "1"]                    # เพิ่มรหัสอาคารที่มีอยู่แล้ว
            + ["5", "99"]                   # ลบรหัสอาคารที่ไม่มีอยู่
            + ["2", "1", "1", "1"]          # เพิ่มรหัสแขกซ้ำ
            + ["2", "2", "1", "3", "5"]     # เพิ่มกลุ่มที่ซ้ำบางรายการ (s=3..7 ทับ 3..5)
            + ["3", "9", "9"]               # นำแขกที่ไม่มีอยู่ออก
            + ["6", "9", "9"]               # ค้นหาแล้วไม่พบ
            + ["7", "9", "9"]               # ค้นด้วยห้องแล้วไม่พบ
            + ["9", "0"]
        )
        self.assertGreaterEqual(text.count("ปฏิเสธ"), 5)
        self.assertIn("ไม่พบแขก (9, 9)", text)
        self.assertIn("ไม่พบผู้พักที่อาคาร 9 ห้อง 9", text)
        self.assertIn("แขกทั้งหมด K = 10", text)       # ข้อมูลเดิมไม่เปลี่ยนเลย

    def test_cannot_remove_last_building(self):
        text, _ = self.run_menu(["1", "1", "4", "0", ""] + ["5", "1"] + ["9", "0"])
        self.assertIn("ปฏิเสธ", text)
        self.assertIn("อาคาร   1: 0 คน", text)         # อาคารสุดท้ายยังอยู่

    def test_no_guests_k_zero(self):
        text, _ = self.run_menu(
            ["1", "3", "4", "1", "0", ""]   # K = 0
            + ["9"]                         # CV ไม่คำนวณ
            + ["4", ""]                     # เพิ่มอาคาร: ย้าย 0 คน อัตราไม่คำนวณ
            + ["8"]                         # รายการห้องว่าง
            + ["0"]
        )
        self.assertIn("CV: ไม่คำนวณ", text)
        self.assertIn("อัตราการย้าย: ไม่คำนวณ", text)
        self.assertIn("ยังไม่มีผู้พัก", text)

    def test_export_without_prerequisites(self):
        text, _ = self.run_menu(INIT_10 + ["12", "2"] + ["12", "3"] + ["12", "9"] + ["0"])
        self.assertEqual(text.count("ข้อมูลไม่ถูกต้อง"), 3)

    def test_input_ends_midway_exits_cleanly(self):
        self.run_menu(["1", "3"])             # input หมดกลางคำสั่ง -> ต้องจบอย่างสุภาพ ไม่ raise
        self.run_menu([])                     # ไม่มี input เลย

    def test_failed_init_keeps_previous_system(self):
        text, menu = self.run_menu(INIT_10 + ["1", "2", "4", "1", "abc", ""] + ["9", "0"])
        self.assertEqual(menu.system.guest_count, 10)


if __name__ == "__main__":
    unittest.main()
