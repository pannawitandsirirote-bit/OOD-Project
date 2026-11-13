"""HashRing — วงแหวน Consistent Hashing พร้อม virtual node

โครงสร้างข้อมูล
- self.__points    : list ของ tuple (pos, node_id, j) เรียงจากน้อยไปมากเสมอ
                     การเรียง tuple ของ Python เทียบ pos ก่อน ถ้าเท่ากันเทียบ node_id แล้วจึง j
                     จึงตรงกับกติกาจุดชนกันของโจทย์ 4.3 ข้อ 4 พอดี
- self.__positions : list ของ pos อย่างเดียว ลำดับเดียวกับ __points ใช้กับ bisect_left
- self.__nodes     : set ของ node_id ที่อยู่ในวงแหวน ตรวจซ้ำ/มีอยู่ได้ O(1)

สัญลักษณ์: N = จำนวนอาคาร, V = virtual node ต่ออาคาร, M = N × V = จำนวนจุดทั้งหมด
"""
from bisect import bisect_left

from .hashing import guest_key, hash64, vnode_key
from .models import (
    DuplicateNodeError,
    InvalidInputError,
    LastNodeError,
    NodeNotFoundError,
)


class HashRing:
    def __init__(self, v: int, salt: str = "", hash_fn=hash64):
        """v = จำนวน virtual node ต่ออาคาร (คงที่ตลอดอายุของวงแหวน)
        salt = ข้อความเติมก่อนแฮช ใช้สร้างตำแหน่งชุดใหม่ในการทดลองแต่ละรอบ
        hash_fn = ฟังก์ชันแฮช (เทสต์ส่งฟังก์ชันปลอมเข้ามาเพื่อกำหนดตำแหน่งเองได้)
        """
        if not isinstance(v, int) or isinstance(v, bool) or v < 1:
            raise InvalidInputError(f"V ต้องเป็นจำนวนเต็ม >= 1 ไม่ใช่ {v!r}")
        self.__v = v
        self.__salt = salt
        self.__hash_fn = hash_fn
        self.__points = []
        self.__positions = []
        self.__nodes = set()

    @property
    def v(self) -> int:
        return self.__v

    @property
    def salt(self) -> str:
        return self.__salt

    # ------------------------------------------------------------------ อาคาร

    def add_node(self, node_id: int) -> None:
        """เพิ่มเฉพาะ V จุดของอาคารใหม่ จุดเดิมไม่ถูกแตะ

        Big-O: แฮช V ครั้ง O(V) + เรียง list ใหม่ O(M log M) + สร้าง __positions O(M)
        รวม O(M log M) กรณีเลวร้ายที่สุด
        (Timsort ของ Python เจอ list เดิมที่เรียงอยู่แล้ว จึงทำงานจริงใกล้ O(M + V log V))
        """
        self.__validate_node_id(node_id)
        if node_id in self.__nodes:
            raise DuplicateNodeError(f"อาคาร {node_id} มีอยู่แล้ว วงแหวนไม่เปลี่ยน")

        new_points = [
            (self.__hash_fn(vnode_key(node_id, j), self.__salt), node_id, j)
            for j in range(self.__v)
        ]
        self.__points.extend(new_points)
        self.__points.sort()                       # เรียงด้วย (pos, node_id, j)
        self.__positions = [p[0] for p in self.__points]
        self.__nodes.add(node_id)

    def remove_node(self, node_id: int) -> None:
        """ลบ V จุดของอาคารนั้นทั้งหมด จุดของอาคารอื่นคงตำแหน่งเดิม

        Big-O: กรอง list ครั้งเดียว O(M)
        """
        self.__validate_node_id(node_id)
        if node_id not in self.__nodes:
            raise NodeNotFoundError(f"ไม่พบอาคาร {node_id}")
        if len(self.__nodes) == 1:
            raise LastNodeError("ลบอาคารสุดท้ายไม่ได้ ต้องมีอาคารอย่างน้อย 1 แห่งเสมอ")

        self.__points = [p for p in self.__points if p[1] != node_id]
        self.__positions = [p[0] for p in self.__points]
        self.__nodes.remove(node_id)

    # ------------------------------------------------------------- เลือกอาคาร

    def locate(self, position: int) -> int:
        """คืน node_id ของจุดแรกที่ตำแหน่ง >= position ถ้าไม่มีให้วนกลับจุดแรกของวงแหวน

        bisect_left คืน index แรกที่ __positions[i] >= position
        ถ้ามีหลายจุดตำแหน่งเท่ากัน จะได้จุดแรกตามลำดับ (pos, node_id, j)

        Big-O: O(log M)
        """
        if not self.__points:
            raise InvalidInputError("วงแหวนยังไม่มีอาคาร")
        i = bisect_left(self.__positions, position)
        if i == len(self.__positions):             # เลยจุดสุดท้าย → วนกลับต้นวงแหวน
            i = 0
        return self.__points[i][1]

    def guest_position(self, c: int, s: int) -> int:
        """ตำแหน่งของแขก (c, s) บนวงแหวน"""
        return self.__hash_fn(guest_key(c, s), self.__salt)

    def node_for(self, c: int, s: int) -> int:
        """คำนวณอาคารของแขกจากวงแหวนปัจจุบันทุกครั้ง ไม่ใช้ค่าที่บันทึกไว้

        Big-O: แฮช O(1) (ถือว่าความยาวรหัสคงที่) + locate O(log M) = O(log M)
        """
        return self.locate(self.guest_position(c, s))

    # ------------------------------------------------------------------ ข้อมูล

    def nodes(self) -> list:
        """รหัสอาคารทั้งหมด เรียงจากน้อยไปมาก — O(N log N)"""
        return sorted(self.__nodes)

    def points(self) -> list:
        """สำเนาจุดทั้งหมด [(pos, node_id, j), ...] ใช้วาดวงแหวนหรือตรวจสอบ — O(M)"""
        return list(self.__points)

    def __contains__(self, node_id) -> bool:
        return node_id in self.__nodes

    def __len__(self) -> int:
        """จำนวนจุดทั้งหมด M = N × V"""
        return len(self.__points)

    @staticmethod
    def __validate_node_id(node_id) -> None:
        if not isinstance(node_id, int) or isinstance(node_id, bool) or node_id < 1:
            raise InvalidInputError(f"node_id ต้องเป็นจำนวนเต็มบวก ไม่ใช่ {node_id!r}")
