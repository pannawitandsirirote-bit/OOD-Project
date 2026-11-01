"""test_edge_cases.py — กรณีขอบหัวข้อ 4.5/6: ต้องแจ้งเหตุผล (raise HotelError), คงข้อมูลเดิม, ไม่หยุดทำงาน"""
import unittest

from hotel.hotel_system import HotelSystem
from hotel.mod_n import ModNRouter
from hotel.models import (DuplicateGuestError, DuplicateNodeError, GuestNotFoundError,
                          HotelError, InvalidInputError, LastNodeError, NodeNotFoundError)


def state(hs):
    """ภาพรวมข้อมูลทั้งหมดของระบบ ใช้เทียบว่า "ไม่เปลี่ยน" """
    return (hs.iter_guests(), hs.list_rooms(), hs.load_stats().per_node, hs._router.nodes(),
            len(hs._router))


class EdgeBase(unittest.TestCase):
    def setUp(self):
        self.hs = HotelSystem.create(4, 8, [30, 30, 30], salt="0")

    def assertRejected(self, exc, func, *args):
        before = state(self.hs)
        with self.assertRaises(exc):
            func(*args)
        self.assertEqual(before, state(self.hs), "ข้อมูลต้องไม่เปลี่ยนหลังถูกปฏิเสธ")
        self.assertTrue(self.hs.check_integrity())


class NodeEdgeCases(EdgeBase):
    def test_add_existing_node(self):
        self.assertRejected(DuplicateNodeError, self.hs.add_node, 2)

    def test_remove_missing_node(self):
        self.assertRejected(NodeNotFoundError, self.hs.remove_node, 99)

    def test_remove_last_node_with_guests(self):
        for n in (1, 2, 3):
            self.hs.remove_node(n)
        self.assertEqual(self.hs.guest_count, 90)
        self.assertRejected(LastNodeError, self.hs.remove_node, 4)

    def test_remove_last_node_without_guests(self):
        hs = HotelSystem.create(1, 4, [])
        with self.assertRaises(LastNodeError):
            hs.remove_node(1)
        self.assertEqual(hs.node_ids(), [1])
        self.assertIsNone(hs.find_by_guest(1, 1))      # ค้นหายังใช้ได้ ไม่วนไม่จบ
        hs.add_guest(1, 1)
        self.assertEqual(hs.find_by_guest(1, 1)[0], 1)

    def test_remove_missing_node_reports_nothing(self):
        # ต้องไม่มีรายงานจำนวนคนย้ายหลุดออกมา: เรียกแล้ว raise ไม่คืน report
        with self.assertRaises(NodeNotFoundError):
            self.hs.remove_node(99)

    def test_invalid_node_ids(self):
        for bad in (0, -1, 1.5, "2", None, True):
            with self.subTest(bad=bad):
                self.assertRejected(InvalidInputError, self.hs.add_node, bad)
                self.assertRejected(InvalidInputError, self.hs.remove_node, bad)

    def test_node_can_be_readded_after_removal(self):
        self.hs.remove_node(2)
        rep = self.hs.add_node(2)
        self.assertTrue(all(m.new_node == 2 for m in rep.moves))
        self.assertTrue(self.hs.check_integrity())

    def test_duplicate_node_does_not_double_ring_points(self):
        n_points = len(self.hs._router)
        with self.assertRaises(DuplicateNodeError):
            self.hs.add_node(1)
        self.assertEqual(len(self.hs._router), n_points)       # M = N*V ยังเท่าเดิม
        self.hs.remove_node(1)
        self.assertEqual(len(self.hs._router), n_points - 8)   # ลบได้หมด ไม่มีจุดตกค้าง

    def test_modn_router_errors(self):
        r = ModNRouter()
        r.add_node(1)
        with self.assertRaises(DuplicateNodeError):
            r.add_node(1)
        with self.assertRaises(NodeNotFoundError):
            r.remove_node(5)
        self.assertEqual(r.nodes(), [1])

    def test_modn_system_edge_cases(self):
        hs = HotelSystem.create(2, 1, [10], method="modn")
        before = state(hs)
        for func, arg, exc in ((hs.add_node, 1, DuplicateNodeError),
                               (hs.remove_node, 9, NodeNotFoundError)):
            with self.assertRaises(exc):
                func(arg)
            self.assertEqual(before, state(hs))
        hs.remove_node(2)
        with self.assertRaises(LastNodeError):
            hs.remove_node(1)


class GuestEdgeCases(EdgeBase):
    def test_duplicate_guest_not_overwritten(self):
        self.assertRejected(DuplicateGuestError, self.hs.add_guest, 1, 1)

    def test_group_with_partial_overlap_rejected_whole(self):
        # (1, 25..34) ทับกับ (1, 25..30) ที่มีอยู่ -> ปฏิเสธทั้งกลุ่ม ห้ามเพิ่ม (1, 31..34)
        self.assertRejected(DuplicateGuestError, self.hs.add_guests, 1, 25, 10)
        self.assertIsNone(self.hs.find_by_guest(1, 31))

    def test_group_overlap_only_last_item(self):
        self.assertRejected(DuplicateGuestError, self.hs.add_guests, 1, 21, 10)  # ชน s=30

    def test_group_count_zero_changes_nothing(self):
        before = state(self.hs)
        self.assertEqual(self.hs.add_guests(1, 1, 0), [])
        self.assertEqual(self.hs.add_guests(9, 1, 0), [])
        self.assertEqual(before, state(self.hs))

    def test_invalid_inputs(self):
        # ค่าที่ README บังคับให้ปฏิเสธ: ติดลบ / ไม่ใช่จำนวนเต็ม / c, s < 1
        cases = [(self.hs.add_guests, (1, 100, -1)), (self.hs.add_guests, (1, 100, 2.5)),
                 (self.hs.add_guests, (1, 100, "3")),
                 (self.hs.add_guests, (0, 100, 3)), (self.hs.add_guests, (1, 0, 3)),
                 (self.hs.add_guest, (0, 1)), (self.hs.add_guest, (1, 0)),
                 (self.hs.add_guest, (-1, 5)), (self.hs.add_guest, (1.0, 5)),
                 (self.hs.add_guest, ("1", 5)), (self.hs.remove_guest, (0, 1))]
        for func, args in cases:
            with self.subTest(func=func.__name__, args=args):
                self.assertRejected(InvalidInputError, func, *args)

    def test_find_with_invalid_code_finds_nothing(self):
        # ค้นหาไม่พบ ต้องคืน None ไม่ให้ error หลุด (รหัสผิดรูปแบบก็ไม่มีแขกอยู่แล้ว)
        self.assertIsNone(self.hs.find_by_guest(0, 1))

    def test_remove_missing_guest_keeps_K(self):
        k = self.hs.guest_count
        self.assertRejected(GuestNotFoundError, self.hs.remove_guest, 7, 7)
        self.assertEqual(self.hs.guest_count, k)

    def test_find_missing_returns_none(self):
        self.assertIsNone(self.hs.find_by_guest(9, 9))
        self.assertIsNone(self.hs.find_by_room(1, 10 ** 9))
        self.assertIsNone(self.hs.find_by_room(99, 1))

    def test_remove_then_readd_is_fresh_stay_using_current_ring(self):
        old_node = self.hs.find_by_guest(1, 1)[0]
        self.hs.remove_guest(1, 1)
        self.assertIsNone(self.hs.find_by_guest(1, 1))
        self.hs.add_node(5)                       # ตอนนี้ (1,1) ไม่อยู่ในระบบ จึงไม่นับเป็นผู้ย้าย
        self.hs.add_guest(1, 1)
        node, room = self.hs.find_by_guest(1, 1)
        self.assertEqual(node, self.hs.compute_node(1, 1))
        self.assertEqual(room, 1)
        self.assertTrue(self.hs.check_integrity())
        self.assertIn(old_node, self.hs.node_ids())

    def test_all_guests_removed_then_stats_and_migration(self):
        for c in (1, 2, 3):
            for s in range(1, 31):
                self.hs.remove_guest(c, s)
        self.assertEqual(self.hs.guest_count, 0)
        rep = self.hs.add_node(5)
        self.assertEqual((rep.moved_count, rep.rate), (0, None))


class EmptySystem(unittest.TestCase):
    def test_K_zero_stats(self):
        hs = HotelSystem.create(3, 8, [])
        st = hs.load_stats()
        self.assertEqual(st.per_node, {1: 0, 2: 0, 3: 0})       # รวมอาคารที่ 0 คน
        self.assertEqual((st.max_load, st.min_load, st.mean, st.std), (0, 0, 0.0, 0.0))
        self.assertIsNone(st.cv)

    def test_stats_with_guests_include_empty_nodes(self):
        hs = HotelSystem.create(3, 1, [1])
        st = hs.load_stats()
        self.assertEqual(sum(st.per_node.values()), 1)
        self.assertEqual(st.min_load, 0)
        self.assertAlmostEqual(st.mean, 1 / 3)
        self.assertIsNotNone(st.cv)

    def test_create_validation(self):
        for args in ((0, 8, []), (-1, 8, []), (2.0, 8, []), (2, 0, []), (2, 8, [-1]),
                     (2, 8, [1.5])):
            with self.subTest(args=args):
                with self.assertRaises(InvalidInputError):
                    HotelSystem.create(*args)
        with self.assertRaises(InvalidInputError):
            HotelSystem.create(2, 8, [], method="bogus")

    def test_all_domain_errors_share_base_class(self):
        for exc in (DuplicateNodeError, NodeNotFoundError, LastNodeError, DuplicateGuestError,
                    GuestNotFoundError, InvalidInputError):
            self.assertTrue(issubclass(exc, HotelError))


if __name__ == "__main__":
    unittest.main()
