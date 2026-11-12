"""ฟังก์ชันแฮชที่ใช้ทั้งระบบ

กติกา (โจทย์ 4.3):
- ใช้ SHA-256 แล้วตัดมาเป็นตำแหน่ง 64 บิต เพื่อให้ค่าคงที่ทุกครั้งที่เปิดโปรแกรม
- ห้ามใช้ hash() ของ Python เพราะสุ่มค่าใหม่ทุกครั้งที่รัน (hash randomization)
- แยกข้อความของแขกกับ virtual node ให้ชัดเจน: "guest:c:s" และ "node:node_id:j"
"""
import hashlib

RING_SIZE = 2 ** 64          # วงแหวนมีตำแหน่ง 0 .. 2^64 - 1


def guest_key(c: int, s: int) -> str:
    """ข้อความที่ใช้แฮชตำแหน่งของแขก (c, s)"""
    return f"guest:{c}:{s}"


def vnode_key(node_id: int, j: int) -> str:
    """ข้อความที่ใช้แฮชตำแหน่งของ virtual node ลำดับที่ j (0..V-1) ของอาคาร node_id"""
    return f"node:{node_id}:{j}"


def hash64(key: str, salt: str = "") -> int:
    """แปลงข้อความเป็นตำแหน่งบนวงแหวน (จำนวนเต็ม 0 .. 2^64 - 1)

    ขั้นตอน:
    1) ถ้ามี salt ให้ต่อหน้าข้อความเป็น "salt|key" (ไม่มี salt ใช้ key ตรง ๆ)
    2) เข้ารหัสข้อความเป็นไบต์แบบ UTF-8
    3) SHA-256 ได้ 32 ไบต์ เอา 8 ไบต์แรก (= 64 บิต)
    4) แปลง 8 ไบต์เป็นจำนวนเต็มแบบ big-endian (ไบต์แรกมีค่าประจำหลักสูงสุด)
    """
    text = key if salt == "" else f"{salt}|{key}"
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")
