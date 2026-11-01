"""test_csv_export.py — จำนวนแถว CSV = จำนวนแขกปัจจุบัน, คอลัมน์ถูก, UTF-8, ไม่มีบรรทัดว่างเกิน"""
import csv
import os
import tempfile
import unittest

from hotel.csv_export import (EXPERIMENT_COLUMNS, GUEST_COLUMNS, MOVE_COLUMNS, export_experiment,
                              export_guests, export_moves)
from hotel.hotel_system import HotelSystem
from hotel.models import ExportError, HotelError, MigrationReport


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


class CsvBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name
        self.hs = HotelSystem.create(4, 16, [120] * 5, salt="0")      # K = 600

    def path(self, name):
        return os.path.join(self.dir, name)


class GuestsCsv(CsvBase):
    def test_header_and_row_count_equal_K(self):
        n = export_guests(self.hs, self.path("g.csv"))
        rows = read_csv(self.path("g.csv"))
        self.assertEqual(rows[0], GUEST_COLUMNS)
        self.assertEqual(rows[0], ["channel_id", "sequence_id", "node_id", "room_no"])
        self.assertEqual(n, self.hs.guest_count)
        self.assertEqual(len(rows) - 1, self.hs.guest_count)

    def test_rows_match_system_and_are_unique(self):
        export_guests(self.hs, self.path("g.csv"))
        rows = [tuple(map(int, r)) for r in read_csv(self.path("g.csv"))[1:]]
        self.assertEqual(len(set((c, s) for c, s, _, _ in rows)), len(rows))
        self.assertEqual(len(set((n, r) for _, _, n, r in rows)), len(rows))   # ที่อยู่ห้องไม่ซ้ำ
        for c, s, n, r in rows:
            self.assertEqual(self.hs.find_by_guest(c, s), (n, r))

    def test_row_count_follows_changes(self):
        self.hs.remove_guest(1, 1)
        self.hs.add_guests(9, 1, 25)
        self.hs.add_node(5)
        self.hs.remove_node(2)
        n = export_guests(self.hs, self.path("g.csv"))
        self.assertEqual(n, self.hs.guest_count)
        self.assertEqual(len(read_csv(self.path("g.csv"))) - 1, self.hs.guest_count)

    def test_empty_system_header_only(self):
        hs = HotelSystem.create(2, 4, [])
        self.assertEqual(export_guests(hs, self.path("e.csv")), 0)
        self.assertEqual(read_csv(self.path("e.csv")), [GUEST_COLUMNS])

    def test_no_blank_lines_newline_empty_mode(self):
        export_guests(self.hs, self.path("g.csv"))
        with open(self.path("g.csv"), "rb") as f:
            raw = f.read()
        self.assertNotIn(b"\r\r\n", raw)                   # ไม่มี \r ซ้อนจากการเปิดแบบไม่ใส่ newline=""
        self.assertEqual(raw.count(b"\n"), self.hs.guest_count + 1)
        raw.decode("utf-8")                                # ถอดรหัส UTF-8 ได้


class MovesCsv(CsvBase):
    def test_rows_equal_moved_count_and_fields(self):
        rep = self.hs.add_node(5)
        n = export_moves(rep, self.path("m.csv"))
        rows = read_csv(self.path("m.csv"))
        self.assertEqual(rows[0], MOVE_COLUMNS)
        self.assertEqual(n, rep.moved_count)
        self.assertEqual(len(rows) - 1, rep.moved_count)
        self.assertGreater(rep.moved_count, 0)
        for row, m in zip(rows[1:], rep.moves):
            self.assertEqual(tuple(map(int, row)), (m.c, m.s, m.old_node, m.new_node, m.room_no))
        for row in rows[1:]:
            self.assertEqual(int(row[3]), 5)               # ผู้ย้ายเข้าอาคารใหม่เท่านั้น

    def test_moves_file_agrees_with_guests_file_after_migration(self):
        rep = self.hs.remove_node(3)
        export_guests(self.hs, self.path("g.csv"))
        export_moves(rep, self.path("m.csv"))
        now = {(int(r[0]), int(r[1])): (int(r[2]), int(r[3])) for r in read_csv(self.path("g.csv"))[1:]}
        for r in read_csv(self.path("m.csv"))[1:]:
            c, s, old, new, room = map(int, r)
            self.assertEqual(now[(c, s)], (new, room))
            self.assertEqual(old, 3)

    def test_no_moves_header_only(self):
        hs = HotelSystem.create(2, 4, [])
        rep = hs.add_node(3)
        self.assertEqual(export_moves(rep, self.path("m.csv")), 0)
        self.assertEqual(read_csv(self.path("m.csv")), [MOVE_COLUMNS])


class ExperimentCsv(CsvBase):
    ROW = {"experiment": "B", "salt": "0", "method": "ring", "K": 10000, "N": 10, "V": 32,
           "metric": "move_rate", "value": 0.0909, "unit": "ratio"}

    def test_roundtrip_with_thai_text(self):
        row2 = dict(self.ROW, metric="หมายเหตุ", unit="อัตราส่วน")
        n = export_experiment([self.ROW, row2], self.path("x.csv"))
        rows = read_csv(self.path("x.csv"))
        self.assertEqual(n, 2)
        self.assertEqual(rows[0], EXPERIMENT_COLUMNS)
        self.assertEqual(rows[2][6:], ["หมายเหตุ", "0.0909", "อัตราส่วน"])
        self.assertEqual(rows[1][:6], ["B", "0", "ring", "10000", "10", "32"])

    def test_missing_column_rejected(self):
        bad = dict(self.ROW)
        del bad["unit"]
        with self.assertRaises(ExportError):
            export_experiment([self.ROW, bad], self.path("x.csv"))
        self.assertFalse(os.path.exists(self.path("x.csv")))      # ไม่เหลือไฟล์ครึ่ง ๆ กลาง ๆ


class ExportFailures(CsvBase):
    def test_unwritable_path_raises_export_error_not_crash(self):
        bad = os.path.join(self.dir, "no_such_dir", "g.csv")
        with self.assertRaises(ExportError):
            export_guests(self.hs, bad)
        with self.assertRaises(HotelError):                       # cli จับด้วย HotelError ได้
            export_moves(MigrationReport("add", 9, 0, []), bad)
        self.assertEqual(self.hs.guest_count, 600)                # ระบบไม่เสียหาย


if __name__ == "__main__":
    unittest.main()
