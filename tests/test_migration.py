"""test_migration.py — เพิ่ม/ลบอาคาร, MigrationReport, ตัวอย่างวงแหวนเล็ก 9.1, เทียบ hash mod N"""
import unittest

from hotel.guest import room_number
from hotel.hash_ring import HashRing
from hotel.hotel_system import HotelSystem
from hotel.mod_n import ModNRouter
from hotel.models import MigrationReport, Move

A, B, C, D = 1, 2, 3, 4
GUEST_POS = [10, 20, 25, 35, 50, 70, 90]          # แขก (1, 1) .. (1, 7)


def fake_hash(table):
    """hash_fn จำลอง: คืนตำแหน่งที่กำหนดไว้ตาม key"""
    return lambda key, salt="": table[key]


def small_ring_system(extra=()):
    table = {"node:1:0": 20, "node:2:0": 50, "node:3:0": 80, "node:4:0": 35}
    table.update({f"guest:1:{i + 1}": p for i, p in enumerate(GUEST_POS)})
    h = fake_hash(table)
    ring = HashRing(1, hash_fn=h)
    for n in (A, B, C, *extra):
        ring.add_node(n)
    hs = HotelSystem(ring)
    hs.add_guests(1, 1, 7)
    return hs


def snapshot(hs):
    return {(c, s): (n, r) for c, s, n, r in hs.iter_guests()}


class SmallRingExample91(unittest.TestCase):
    def test_initial_assignment(self):
        hs = small_ring_system()
        expect = [A, A, B, B, B, C, A]            # คอลัมน์ "เริ่มต้น" ในตาราง 9.1 (90 วนกลับไป A)
        self.assertEqual([hs.find_by_guest(1, s)[0] for s in range(1, 8)], expect)

    def test_add_D_moves_two_into_D_only(self):
        hs = small_ring_system()
        before = snapshot(hs)
        rep = hs.add_node(D)
        self.assertEqual(rep.moved_count, 2)
        self.assertEqual({(m.c, m.s) for m in rep.moves}, {(1, 3), (1, 4)})   # ตำแหน่ง 25, 35
        self.assertTrue(all(m.new_node == D and m.old_node == B for m in rep.moves))
        after = snapshot(hs)
        for key in before:
            self.assertEqual(before[key][1], after[key][1])                    # room_no คงเดิม
        self.assertEqual([hs.find_by_guest(1, s)[0] for s in range(1, 8)], [A, A, D, D, B, C, A])
        self.assertTrue(hs.check_integrity())

    def test_remove_B_moves_three_all_from_B(self):
        hs = small_ring_system()
        before = snapshot(hs)
        rep = hs.remove_node(B)
        self.assertEqual(rep.moved_count, 3)
        self.assertEqual({(m.c, m.s) for m in rep.moves}, {(1, 3), (1, 4), (1, 5)})  # 25, 35, 50
        self.assertTrue(all(m.old_node == B and m.new_node == C for m in rep.moves))
        after = snapshot(hs)
        for key in before:
            self.assertEqual(before[key][1], after[key][1])
        self.assertEqual([hs.find_by_guest(1, s)[0] for s in range(1, 8)], [A, A, C, C, C, C, A])
        self.assertTrue(hs.check_integrity())

    def test_rate_matches_moved_over_K(self):
        hs = small_ring_system()
        self.assertAlmostEqual(hs.add_node(D).rate, 2 / 7)


class RingMigrationV32(unittest.TestCase):
    def setUp(self):
        self.hs = HotelSystem.create(5, 32, [300] * 10, salt="0")       # K = 3000

    def test_add_node_only_moves_into_new_node(self):
        before = snapshot(self.hs)
        k = self.hs.guest_count
        rep = self.hs.add_node(6)
        after = snapshot(self.hs)
        self.assertEqual(self.hs.guest_count, k)                          # แขกไม่หายไม่เพิ่ม
        self.assertEqual(rep.total_guests, k)
        self.assertGreater(rep.moved_count, 0)
        self.assertTrue(all(m.new_node == 6 for m in rep.moves))
        self.assertEqual(rep.moved_count, len(rep.moves))
        changed = {key for key in before if before[key][0] != after[key][0]}
        self.assertEqual(changed, {(m.c, m.s) for m in rep.moves})        # ไม่มีใครย้ายนอกรายการ
        self.assertTrue(all(before[k_][1] == after[k_][1] for k_ in before))   # room_no คงเดิม
        self.assertEqual(self.hs.load_stats().per_node[6], rep.moved_count)
        self.assertTrue(self.hs.check_integrity())

    def test_remove_node_only_moves_guests_of_that_node(self):
        before = snapshot(self.hs)
        victims = {key for key, (n, _) in before.items() if n == 3}
        rep = self.hs.remove_node(3)
        after = snapshot(self.hs)
        self.assertEqual({(m.c, m.s) for m in rep.moves}, victims)
        self.assertTrue(all(m.old_node == 3 and m.new_node != 3 for m in rep.moves))
        for key in before:
            if key not in victims:
                self.assertEqual(before[key], after[key])                 # อาคารอื่นไม่ขยับ
        self.assertNotIn(3, self.hs.load_stats().per_node)
        self.assertEqual(self.hs.guest_count, 3000)
        self.assertTrue(self.hs.check_integrity())

    def test_add_then_remove_same_node_restores_everything(self):
        before = snapshot(self.hs)
        self.hs.add_node(6)
        self.hs.remove_node(6)
        self.assertEqual(before, snapshot(self.hs))

    def test_moves_agree_with_compute_node(self):
        rep = self.hs.add_node(6)
        for m in rep.moves:
            self.assertEqual(self.hs.compute_node(m.c, m.s), m.new_node)
            self.assertEqual(self.hs.find_by_room(m.new_node, m.room_no), (m.c, m.s))
            self.assertIsNone(self.hs.find_by_room(m.old_node, m.room_no))
            self.assertEqual(m.room_no, room_number(m.c, m.s))

    def test_search_still_correct_after_migration(self):
        self.hs.add_node(6)
        for c, s, n, r in self.hs.iter_guests():
            self.assertEqual(self.hs.find_by_guest(c, s), (n, r))
            self.assertEqual(self.hs.find_by_room(n, r), (c, s))
            self.assertEqual(self.hs.compute_node(c, s), n)

    def test_new_guests_do_not_move_existing_ones(self):
        before = snapshot(self.hs)
        self.hs.add_guests(1, 301, 50)            # ช่องทางเดิม
        self.hs.add_guests(11, 1, 50)             # ช่องทางใหม่
        after = snapshot(self.hs)
        for key, value in before.items():
            self.assertEqual(after[key], value)

    def test_moves_sorted_and_report_fields(self):
        rep = self.hs.add_node(6)
        self.assertEqual(rep.action, "add")
        self.assertEqual(rep.node_id, 6)
        keys = [(m.c, m.s) for m in rep.moves]
        self.assertEqual(keys, sorted(keys))
        self.assertIsInstance(rep.moves[0], Move)


class ModNMigration(unittest.TestCase):
    def test_router_index_semantics_with_fake_hash(self):
        h = fake_hash({"guest:1:1": 10, "guest:1:2": 11, "guest:1:3": 12})
        r = ModNRouter(hash_fn=h)
        for n in (1, 2, 3):
            r.add_node(n)
        self.assertEqual([r.node_for(1, s) for s in (1, 2, 3)], [2, 3, 1])   # 10%3=1, 11%3=2, 12%3=0
        r.remove_node(2)                                                      # list = [1, 3]
        self.assertEqual(r.nodes(), [1, 3])
        self.assertEqual([r.node_for(1, s) for s in (1, 2, 3)], [1, 3, 1])   # %2 -> 0, 1, 0
        r.add_node(7)                                                         # ต่อท้าย: [1, 3, 7]
        self.assertEqual([r.node_for(1, s) for s in (1, 2, 3)], [3, 7, 1])   # list [1,3,7]: 10%3=1, 11%3=2, 12%3=0

    def test_modn_compares_by_real_node_id_not_index(self):
        # ลบ node 1 ออกจาก [1,2,3]: ดัชนีของ 2,3 เลื่อน แต่ถ้าแขกยังอยู่ node เดิมต้องไม่นับว่าย้าย
        h = fake_hash({"guest:1:1": 0, "guest:1:2": 1, "guest:1:3": 2})
        r = ModNRouter(hash_fn=h)
        for n in (1, 2, 3):
            r.add_node(n)
        hs = HotelSystem(r)
        hs.add_guests(1, 1, 3)                     # -> nodes 1, 2, 3
        rep = hs.remove_node(1)                    # list [2,3]: 0%2->2, 1%2->3, 2%2->2
        self.assertEqual({(m.c, m.s): (m.old_node, m.new_node) for m in rep.moves},
                         {(1, 1): (1, 2), (1, 2): (2, 3), (1, 3): (3, 2)})
        self.assertTrue(hs.check_integrity())

    def test_modn_moves_far_more_than_ring(self):
        ring = HotelSystem.create(10, 32, [200] * 10, salt="0", method="ring")
        modn = HotelSystem.create(10, 32, [200] * 10, salt="0", method="modn")
        rr, rm = ring.add_node(11), modn.add_node(11)
        self.assertEqual(rr.total_guests, rm.total_guests)
        self.assertGreater(rm.moved_count, 3 * rr.moved_count)
        self.assertTrue(ring.check_integrity() and modn.check_integrity())

    def test_modn_remove_keeps_every_guest_and_integrity(self):
        hs = HotelSystem.create(5, 1, [200] * 10, salt="1", method="modn")
        rep = hs.remove_node(2)
        self.assertEqual(hs.guest_count, 2000)
        self.assertEqual(rep.moved_count, len(rep.moves))
        self.assertTrue(all(m.old_node != m.new_node for m in rep.moves))
        self.assertNotIn(2, {n for _, _, n, _ in hs.iter_guests()})
        self.assertTrue(hs.check_integrity())

    def test_same_salt_same_hash_for_both_methods(self):
        a = HotelSystem.create(5, 32, [10] * 3, salt="2", method="ring")
        b = HotelSystem.create(5, 32, [10] * 3, salt="2", method="modn")
        self.assertEqual(sorted((c, s, r) for c, s, _, r in a.iter_guests()),
                         sorted((c, s, r) for c, s, _, r in b.iter_guests()))


class ReportBehaviour(unittest.TestCase):
    def test_empty_system_reports_zero_and_no_rate(self):
        hs = HotelSystem.create(3, 8, [])
        rep = hs.add_node(4)
        self.assertEqual((rep.moved_count, rep.total_guests, rep.rate), (0, 0, None))
        self.assertIn("ไม่คำนวณอัตรา", rep.describe())
        rep = hs.remove_node(4)
        self.assertEqual((rep.moved_count, rep.rate), (0, None))

    def test_moved_count_is_always_len_moves(self):
        rep = MigrationReport("add", 9, 10, [Move(1, 1, 1, 9, 1)])
        self.assertEqual(rep.moved_count, 1)
        rep.moves.append(Move(1, 2, 2, 9, 3))
        self.assertEqual(rep.moved_count, 2)
        self.assertAlmostEqual(rep.rate, 0.2)

    def test_describe_contains_numbers(self):
        text = MigrationReport("remove", 3, 10, [Move(1, 1, 3, 1, 1)]).describe()
        self.assertIn("ลบอาคาร 3", text)
        self.assertIn("ย้าย 1 คน", text)
        self.assertIn("10.00%", text)


if __name__ == "__main__":
    unittest.main()
