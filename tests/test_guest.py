import unittest

from hotel.guest import Guest, room_number
from hotel.models import InvalidInputError

class TestRoomNumber(unittest.TestCase):
    def test_table_values_from_readme(self):
        self.assertEqual(room_number(1, 1), 1)
        self.assertEqual(room_number(2, 1), 2)
        self.assertEqual(room_number(1, 2), 3)
        self.assertEqual(room_number(3, 1), 4)
        self.assertEqual(room_number(2, 2), 5)

    def test_no_collisions_over_a_grid(self):
        seen = set()
        for c in range(1, 25):
            for s in range(1, 25):
                room = room_number(c, s)
                self.assertNotIn(room, seen, f"ชนกันที่ (c={c}, s={s}) -> {room}")
                seen.add(room)

    def test_result_is_pure_integer(self):
        room = room_number(7, 9)
        self.assertIsInstance(room, int)

    def test_rejects_zero_or_negative(self):
        with self.assertRaises(InvalidInputError):
            room_number(0, 1)
        with self.assertRaises(InvalidInputError):
            room_number(1, 0)
        with self.assertRaises(InvalidInputError):
            room_number(-1, 1)
        with self.assertRaises(InvalidInputError):
            room_number(1, -1)

    def test_rejects_non_integer(self):
        with self.assertRaises(InvalidInputError):
            room_number(1.5, 1)
        with self.assertRaises(InvalidInputError):
            room_number(1, "2")

class TestGuestDataclass(unittest.TestCase):
    def test_create_fills_room_no_and_key(self):
        g = Guest.create(2, 1)
        self.assertEqual((g.c, g.s), (2, 1))
        self.assertEqual(g.room_no, 2)
        self.assertEqual(g.key, "guest:2:1")

    def test_is_frozen(self):
        g = Guest.create(1, 1)
        with self.assertRaises(Exception):
            g.c = 999

    def test_different_codes_never_share_room(self):
        codes = [(1, 1), (2, 1), (1, 2), (3, 1), (2, 2)]
        guests = [Guest.create(c, s) for c, s in codes]
        rooms = [g.room_no for g in guests]
        self.assertEqual(len(rooms), len(set(rooms)))

if __name__ == "__main__":
    unittest.main()