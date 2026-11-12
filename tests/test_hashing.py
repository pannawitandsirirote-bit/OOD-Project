"""ทดสอบ hotel/hashing.py

รัน: python -m unittest tests.test_hashing -v
"""
import hashlib
import unittest

from hotel.hashing import RING_SIZE, guest_key, hash64, vnode_key


class TestKeys(unittest.TestCase):
    def test_guest_key_format(self):
        self.assertEqual(guest_key(3, 15), "guest:3:15")

    def test_vnode_key_format(self):
        self.assertEqual(vnode_key(7, 0), "node:7:0")
        self.assertEqual(vnode_key(7, 31), "node:7:31")

    def test_guest_and_vnode_keys_never_equal(self):
        # ข้อความของแขกกับ virtual node ต้องแยกกันชัดเจน (โจทย์ 4.3 ข้อ 2)
        self.assertNotEqual(guest_key(1, 0), vnode_key(1, 0))


class TestHash64(unittest.TestCase):
    def test_fixed_values_across_runs(self):
        # ค่าคงที่ที่จดไว้ล่วงหน้า: ถ้าเผลอใช้ hash() ของ Python เทสต์นี้จะพังทุกครั้งที่เปิดใหม่
        self.assertEqual(hash64("guest:1:1"), 3062031282815716176)
        self.assertEqual(hash64("node:1:0"), 3505680375118999729)
        self.assertEqual(hash64("guest:1:1", "0"), 3912152983899886038)

    def test_matches_sha256_first_8_bytes(self):
        # คำนวณอีกวิธีจาก hexdigest: 16 ตัวอักษรฐาน 16 แรก = 8 ไบต์แรก
        for key in ["guest:2:9", "node:10:31", "ภาษาไทย"]:
            expected = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:16], 16)
            self.assertEqual(hash64(key), expected)

    def test_range_is_64_bit(self):
        for c in range(1, 21):
            for s in range(1, 51):
                h = hash64(guest_key(c, s))
                self.assertGreaterEqual(h, 0)
                self.assertLess(h, RING_SIZE)

    def test_same_input_same_output(self):
        self.assertEqual(hash64("guest:5:5", "1"), hash64("guest:5:5", "1"))

    def test_salt_changes_position(self):
        key = guest_key(1, 1)
        self.assertNotEqual(hash64(key, "0"), hash64(key, "1"))
        self.assertNotEqual(hash64(key, "1"), hash64(key, "2"))

    def test_empty_salt_equals_plain_key(self):
        key = guest_key(4, 2)
        expected = int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8], "big")
        self.assertEqual(hash64(key, ""), expected)
        self.assertEqual(hash64(key), expected)


if __name__ == "__main__":
    unittest.main()
