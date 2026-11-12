import unittest

from hotel.hotel_system import HotelSystem
from hotel.models import DuplicateGuestError, GuestNotFoundError, InvalidInputError

class FakeRouter:
    def __init__(self, mapping=None, nodes=(1, 2, 3)):
        self._mapping = dict(mapping or {})
        self._nodes = list(nodes)

    def node_for(self, c, s):
        return self._mapping.get((c, s), self._nodes[0])

    def add_node(self, node_id):
        self._nodes.append(node_id)

    def remove_node(self, node_id):
        self._nodes.remove(node_id)

    def nodes(self):
        return list(self._nodes)

    def __len__(self):
        return len(self._nodes)

class TestHotelSystemGuests(unittest.TestCase):
    def setUp(self):
        self.router = FakeRouter(nodes=(1, 2, 3))
        self.system = HotelSystem(self.router)

    def test_add_guest_basic(self):
        guest = self.system.add_guest(1, 1)
        self.assertEqual(guest.room_no, 1)
        self.assertEqual(self.system.guest_count, 1)
        self.assertEqual(self.system.find_by_guest(1, 1), (1, 1))

    def test_add_guest_duplicate_rejected(self):
        self.system.add_guest(1, 1)
        with self.assertRaises(DuplicateGuestError):
            self.system.add_guest(1, 1)
        self.assertEqual(self.system.guest_count, 1)

    def test_existing_guest_address_unchanged_when_new_guest_added(self):
        self.system.add_guest(1, 1)
        before = self.system.find_by_guest(1, 1)
        self.system.add_guest(1, 2)
        self.system.add_guest(2, 1)
        after = self.system.find_by_guest(1, 1)
        self.assertEqual(before, after)

    def test_invalid_guest_code_rejected(self):
        with self.assertRaises(InvalidInputError):
            self.system.add_guest(0, 1)
        with self.assertRaises(InvalidInputError):
            self.system.add_guest(1, -5)

    def test_add_guests_group_success(self):
        guests = self.system.add_guests(1, 1, 3)
        self.assertEqual(len(guests), 3)
        self.assertEqual(self.system.guest_count, 3)
        self.assertEqual([g.s for g in guests], [1, 2, 3])

    def test_add_guests_group_zero_is_noop(self):
        result = self.system.add_guests(1, 1, 0)
        self.assertEqual(result, [])
        self.assertEqual(self.system.guest_count, 0)

    def test_add_guests_group_partial_duplicate_rejects_whole_group(self):
        self.system.add_guest(1, 2)
        with self.assertRaises(DuplicateGuestError):
            self.system.add_guests(1, 1, 3)
        self.assertEqual(self.system.guest_count, 1)
        self.assertIsNone(self.system.find_by_guest(1, 1))
        self.assertIsNone(self.system.find_by_guest(1, 3))

    def test_add_guests_negative_count_is_invalid(self):
        with self.assertRaises(InvalidInputError):
            self.system.add_guests(1, 1, -1)

    def test_remove_guest(self):
        self.system.add_guest(1, 1)
        removed = self.system.remove_guest(1, 1)
        self.assertEqual((removed.c, removed.s), (1, 1))
        self.assertEqual(self.system.guest_count, 0)
        self.assertIsNone(self.system.find_by_guest(1, 1))

    def test_remove_nonexistent_guest_raises_and_k_unchanged(self):
        self.system.add_guest(9, 9)
        with self.assertRaises(GuestNotFoundError):
            self.system.remove_guest(1, 1)
        self.assertEqual(self.system.guest_count, 1)

    def test_remove_then_readd_same_code_is_fresh_stay(self):
        self.system.add_guest(1, 1)
        self.system.remove_guest(1, 1)
        guest = self.system.add_guest(1, 1)
        self.assertEqual(self.system.guest_count, 1)
        self.assertEqual(guest.room_no, 1)

    def test_find_by_room_round_trip(self):
        self.system.add_guest(2, 1)
        node_room = self.system.find_by_guest(2, 1)
        self.assertEqual(self.system.find_by_room(*node_room), (2, 1))

    def test_find_returns_none_when_not_found(self):
        self.assertIsNone(self.system.find_by_guest(5, 5))
        self.assertIsNone(self.system.find_by_room(1, 999))

    def test_compute_node_uses_router_directly(self):
        router = FakeRouter(mapping={(1, 1): 2}, nodes=(1, 2, 3))
        system = HotelSystem(router)
        self.assertEqual(system.compute_node(1, 1), 2)
        self.assertEqual(system.guest_count, 0)

    def test_list_rooms_sorted_by_node_then_room(self):
        router = FakeRouter(mapping={(1, 1): 2, (2, 1): 1}, nodes=(1, 2, 3))
        system = HotelSystem(router)
        system.add_guest(1, 1)
        system.add_guest(2, 1)
        rows = system.list_rooms()
        self.assertEqual(rows, [(1, 2, 2, 1), (2, 1, 1, 1)])

    def test_load_stats_when_no_guests(self):
        stats = self.system.load_stats()
        self.assertEqual(stats.max_load, 0)
        self.assertEqual(stats.min_load, 0)
        self.assertIsNone(stats.cv)
        self.assertEqual(set(stats.per_node.keys()), {1, 2, 3})

    def test_load_stats_includes_zero_load_nodes(self):
        self.system.add_guest(1, 1)
        stats = self.system.load_stats()
        self.assertEqual(stats.per_node[1], 1)
        self.assertEqual(stats.per_node[2], 0)
        self.assertEqual(stats.per_node[3], 0)
        self.assertEqual(sum(stats.per_node.values()), self.system.guest_count)

    def test_internal_consistency_lengths_match(self):
        self.system.add_guests(1, 1, 5)
        self.system.add_guests(2, 1, 3)
        stats = self.system.load_stats()
        self.assertEqual(self.system.guest_count, len(self.system.list_rooms()))
        self.assertEqual(self.system.guest_count, sum(stats.per_node.values()))

class TestHotelSystemWithRealHashRing(unittest.TestCase):
    def setUp(self):
        from hotel.hash_ring import HashRing
        self.ring = HashRing(v=8, salt="test")
        for node_id in (1, 2, 3):
            self.ring.add_node(node_id)
        self.system = HotelSystem(self.ring)

    def test_round_trip_many_guests_no_collision(self):
        for c in range(1, 6):
            for s in range(1, 6):
                self.system.add_guest(c, s)
        self.assertEqual(self.system.guest_count, 25)

        for c in range(1, 6):
            for s in range(1, 6):
                node_room = self.system.find_by_guest(c, s)
                self.assertIsNotNone(node_room)
                self.assertEqual(self.system.find_by_room(*node_room), (c, s))

if __name__ == "__main__":
    unittest.main()