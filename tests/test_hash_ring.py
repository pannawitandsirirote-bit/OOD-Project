"""ทดสอบ hotel/hash_ring.py

รัน: python -m unittest tests.test_hash_ring -v
"""
import unittest

from hotel.hash_ring import HashRing
from hotel.hashing import guest_key, vnode_key
from hotel.hotel_system import HotelSystem
from hotel.models import (
    DuplicateNodeError,
    InvalidInputError,
    LastNodeError,
    NodeNotFoundError,
)

# รหัสอาคารในตัวอย่างหัวข้อ 9.1
A, B, C, D = 1, 2, 3, 4


def fake_hash(positions: dict):
    """สร้างฟังก์ชันแฮชปลอมที่คืนตำแหน่งตาม dict (ไม่สน salt)"""
    def _hash(key, salt=""):
        return positions[key]
    return _hash


def small_ring_positions() -> dict:
    """วงแหวนขนาด 100, V = 1 : A ที่ 20, B ที่ 50, C ที่ 80, D ที่ 35
    แขก (1,1)..(1,7) อยู่ที่ 10, 20, 25, 35, 50, 70, 90 ตามตารางโจทย์"""
    positions = {
        vnode_key(A, 0): 20,
        vnode_key(B, 0): 50,
        vnode_key(C, 0): 80,
        vnode_key(D, 0): 35,
    }
    for s, pos in enumerate([10, 20, 25, 35, 50, 70, 90], start=1):
        positions[guest_key(1, s)] = pos
    return positions


def build_abc() -> HashRing:
    ring = HashRing(v=1, hash_fn=fake_hash(small_ring_positions()))
    for node_id in (A, B, C):
        ring.add_node(node_id)
    return ring


GUESTS_9_1 = [(1, s) for s in range(1, 8)]


class TestSmallRingExample(unittest.TestCase):
    """ตัวอย่างวงแหวนเล็ก หัวข้อ 9.1 — ทุกกรณีเริ่มจากสถานะ A B C ใหม่"""

    def test_initial_assignment(self):
        ring = build_abc()
        got = [ring.node_for(c, s) for c, s in GUESTS_9_1]
        self.assertEqual(got, [A, A, B, B, B, C, A])

    def test_add_d_moves_two_guests_into_d_only(self):
        ring = build_abc()
        before = {g: ring.node_for(*g) for g in GUESTS_9_1}
        ring.add_node(D)
        after = {g: ring.node_for(*g) for g in GUESTS_9_1}
        self.assertEqual([after[g] for g in GUESTS_9_1], [A, A, D, D, B, C, A])
        moved = [g for g in GUESTS_9_1 if before[g] != after[g]]
        self.assertEqual(len(moved), 2)
        self.assertTrue(all(after[g] == D for g in moved))

    def test_remove_b_moves_three_guests_only_from_b(self):
        ring = build_abc()
        before = {g: ring.node_for(*g) for g in GUESTS_9_1}
        ring.remove_node(B)
        after = {g: ring.node_for(*g) for g in GUESTS_9_1}
        self.assertEqual([after[g] for g in GUESTS_9_1], [A, A, C, C, C, C, A])
        moved = [g for g in GUESTS_9_1 if before[g] != after[g]]
        self.assertEqual(len(moved), 3)
        self.assertTrue(all(before[g] == B for g in moved))


class TestLocate(unittest.TestCase):
    def setUp(self):
        self.ring = build_abc()            # A=20, B=50, C=80

    def test_exactly_on_point(self):
        self.assertEqual(self.ring.locate(20), A)
        self.assertEqual(self.ring.locate(50), B)
        self.assertEqual(self.ring.locate(80), C)

    def test_between_points(self):
        self.assertEqual(self.ring.locate(21), B)
        self.assertEqual(self.ring.locate(79), C)

    def test_before_first_point(self):
        self.assertEqual(self.ring.locate(0), A)

    def test_after_last_point_wraps_around(self):
        self.assertEqual(self.ring.locate(81), A)
        self.assertEqual(self.ring.locate(99), A)

    def test_empty_ring_rejected(self):
        ring = HashRing(v=4)
        with self.assertRaises(InvalidInputError):
            ring.locate(0)


class TestCollisions(unittest.TestCase):
    """จุดที่แฮชชนกันต้องเก็บไว้ทุกจุด และเรียงด้วย (pos, node_id, j)"""

    def test_same_position_picks_smaller_node_id(self):
        positions = {vnode_key(1, 0): 50, vnode_key(2, 0): 50, vnode_key(3, 0): 80}
        ring = HashRing(v=1, hash_fn=fake_hash(positions))
        for node_id in (2, 3, 1):          # เพิ่มสลับลำดับ ผลต้องไม่เปลี่ยน
            ring.add_node(node_id)
        self.assertEqual(len(ring), 3)     # เก็บไว้ครบทุกจุด
        self.assertEqual(ring.locate(50), 1)
        self.assertEqual(ring.locate(40), 1)
        self.assertEqual(ring.locate(51), 3)

    def test_same_node_same_position_picks_smaller_j(self):
        positions = {vnode_key(1, 0): 70, vnode_key(1, 1): 30,
                     vnode_key(2, 0): 30, vnode_key(2, 1): 90}
        ring = HashRing(v=2, hash_fn=fake_hash(positions))
        ring.add_node(2)
        ring.add_node(1)
        self.assertEqual(ring.points()[:2], [(30, 1, 1), (30, 2, 0)])
        self.assertEqual(ring.locate(30), 1)

    def test_remove_one_of_colliding_nodes(self):
        positions = {vnode_key(1, 0): 50, vnode_key(2, 0): 50, vnode_key(3, 0): 80}
        ring = HashRing(v=1, hash_fn=fake_hash(positions))
        for node_id in (1, 2, 3):
            ring.add_node(node_id)
        ring.remove_node(1)
        self.assertEqual(ring.locate(50), 2)

    def test_many_guests_same_position_get_different_rooms(self):
        positions = {vnode_key(1, 0): 50, vnode_key(2, 0): 80,
                     guest_key(1, 1): 10, guest_key(2, 1): 10, guest_key(1, 2): 10}
        ring = HashRing(v=1, hash_fn=fake_hash(positions))
        ring.add_node(1)
        ring.add_node(2)
        hotel = HotelSystem(ring)
        rooms = [hotel.add_guest(c, s).room_no for c, s in [(1, 1), (2, 1), (1, 2)]]
        self.assertEqual(len(set(rooms)), 3)
        self.assertEqual({hotel.find_by_guest(c, s)[0] for c, s in [(1, 1), (2, 1), (1, 2)]}, {1})


class TestRealHashWithVirtualNodes(unittest.TestCase):
    """ใช้ SHA-256 จริง, V > 1 : ตรวจกติกาการย้ายของโจทย์ 4.4"""

    GUESTS = [(c, s) for c in range(1, 11) for s in range(1, 201)]   # 2,000 คน

    def build(self, n=5, v=16, salt="0"):
        ring = HashRing(v=v, salt=salt)
        for node_id in range(1, n + 1):
            ring.add_node(node_id)
        return ring

    def test_point_count_is_n_times_v(self):
        ring = self.build(n=5, v=16)
        self.assertEqual(len(ring), 80)
        self.assertEqual(ring.nodes(), [1, 2, 3, 4, 5])

    def test_points_sorted(self):
        pts = self.build().points()
        self.assertEqual(pts, sorted(pts))

    def test_add_node_moves_guests_only_into_new_node(self):
        ring = self.build()
        before = {g: ring.node_for(*g) for g in self.GUESTS}
        ring.add_node(6)
        after = {g: ring.node_for(*g) for g in self.GUESTS}
        moved = [g for g in self.GUESTS if before[g] != after[g]]
        self.assertGreater(len(moved), 0)
        self.assertTrue(all(after[g] == 6 for g in moved))

    def test_remove_node_moves_only_its_guests(self):
        ring = self.build()
        before = {g: ring.node_for(*g) for g in self.GUESTS}
        ring.remove_node(3)
        after = {g: ring.node_for(*g) for g in self.GUESTS}
        for g in self.GUESTS:
            if before[g] == 3:
                self.assertNotEqual(after[g], 3)
            else:
                self.assertEqual(after[g], before[g])

    def test_remaining_points_unchanged_after_add_and_remove(self):
        ring = self.build()
        old = set(ring.points())
        ring.add_node(6)
        self.assertTrue(old.issubset(set(ring.points())))
        ring.remove_node(6)
        self.assertEqual(set(ring.points()), old)

    def test_add_order_does_not_matter(self):
        r1 = HashRing(v=8, salt="1")
        r2 = HashRing(v=8, salt="1")
        for node_id in [1, 2, 3, 4]:
            r1.add_node(node_id)
        for node_id in [4, 2, 3, 1]:
            r2.add_node(node_id)
        self.assertEqual(r1.points(), r2.points())

    def test_different_salt_gives_different_ring(self):
        self.assertNotEqual(self.build(salt="0").points(), self.build(salt="1").points())


class TestEdgeCases(unittest.TestCase):
    def setUp(self):
        self.ring = HashRing(v=4)
        self.ring.add_node(1)
        self.ring.add_node(2)

    def test_add_existing_node_rejected_and_ring_unchanged(self):
        snapshot = self.ring.points()
        with self.assertRaises(DuplicateNodeError):
            self.ring.add_node(1)
        self.assertEqual(self.ring.points(), snapshot)

    def test_remove_missing_node_rejected_and_ring_unchanged(self):
        snapshot = self.ring.points()
        with self.assertRaises(NodeNotFoundError):
            self.ring.remove_node(99)
        self.assertEqual(self.ring.points(), snapshot)

    def test_remove_last_node_rejected(self):
        self.ring.remove_node(2)
        with self.assertRaises(LastNodeError):
            self.ring.remove_node(1)
        self.assertEqual(len(self.ring), 4)

    def test_invalid_v_rejected(self):
        for bad in (0, -1, 1.5, "8", True):
            with self.assertRaises(InvalidInputError):
                HashRing(v=bad)

    def test_invalid_node_id_rejected(self):
        for bad in (0, -3, 2.0, "3", True):
            with self.assertRaises(InvalidInputError):
                self.ring.add_node(bad)


class TestWithHotelSystem(unittest.TestCase):
    """ตัวอย่าง 9.1 ผ่าน HotelSystem จริง: นับการย้าย เลขห้องคงเดิม ดัชนีสอดคล้อง"""

    def make_hotel(self):
        hotel = HotelSystem(build_abc())
        for c, s in GUESTS_9_1:
            hotel.add_guest(c, s)
        return hotel

    def test_add_d(self):
        hotel = self.make_hotel()
        rooms_before = {g: hotel.find_by_guest(*g)[1] for g in GUESTS_9_1}
        report = hotel.add_node(D)
        self.assertEqual(report.moved_count, 2)
        self.assertEqual(len(report.moves), report.moved_count)
        self.assertAlmostEqual(report.rate, 2 / 7)
        for m in report.moves:
            self.assertEqual(m.new_node, D)
            self.assertEqual(m.room_no, rooms_before[(m.c, m.s)])
            self.assertEqual(hotel.find_by_room(D, m.room_no), (m.c, m.s))
        self.assertEqual(hotel.guest_count, 7)
        self.assertTrue(hotel.check_integrity())

    def test_remove_b(self):
        hotel = self.make_hotel()
        report = hotel.remove_node(B)
        self.assertEqual(report.moved_count, 3)
        self.assertTrue(all(m.old_node == B for m in report.moves))
        self.assertEqual(hotel.guest_count, 7)
        self.assertTrue(hotel.check_integrity())

    def test_create_with_ring(self):
        hotel = HotelSystem.create(n_nodes=10, v=32, guests_per_channel=[100] * 10, salt="0")
        self.assertEqual(hotel.guest_count, 1000)
        self.assertEqual(sum(hotel.load_stats().per_node.values()), 1000)
        self.assertTrue(hotel.check_integrity())


if __name__ == "__main__":
    unittest.main()
