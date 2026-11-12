"""ชนิดข้อมูลร่วมของระบบ: ข้อผิดพลาด, รายการย้าย, รายงานการย้าย และสถิติโหลด

Move / MigrationReport / LoadStats เก็บค่าเป็นแอตทริบิวต์ private (ขึ้นต้นด้วย _)
และให้อ่านผ่าน property อย่างเดียว สร้างแล้วแก้ค่าจากข้างนอกไม่ได้
ผลลัพธ์ที่รายงานออกไป (จำนวนย้าย, อัตรา, รายการย้าย) จึงตรงกับตอนที่คำนวณเสมอ
"""


class HotelError(Exception):
    """แม่ของข้อผิดพลาดที่ต้อง "ปฏิเสธอย่างสุภาพ" — cli จับแล้วแสดงข้อความ"""


class DuplicateNodeError(HotelError):
    """เพิ่มรหัสอาคารที่มีอยู่แล้ว"""


class NodeNotFoundError(HotelError):
    """ลบรหัสอาคารที่ไม่มีอยู่"""


class LastNodeError(HotelError):
    """ลบอาคารสุดท้าย (ต้องมี N >= 1 เสมอ)"""


class DuplicateGuestError(HotelError):
    """เพิ่มรหัสแขกซ้ำ"""


class GuestNotFoundError(HotelError):
    """นำแขกที่ไม่มีอยู่ออก"""


class InvalidInputError(HotelError):
    """ค่าติดลบ, ไม่ใช่จำนวนเต็ม, c/s < 1, V < 1 ฯลฯ"""


class ExportError(HotelError):
    """ส่งออกไฟล์ไม่ได้ (path เขียนไม่ได้, ข้อมูลคอลัมน์ไม่ครบ)"""


class Move:
    """แขก 1 คนที่เปลี่ยนอาคาร (room_no คงเดิมเสมอ)"""

    __slots__ = ("_c", "_s", "_old_node", "_new_node", "_room_no")

    def __init__(self, c: int, s: int, old_node: int, new_node: int, room_no: int):
        self._c = c
        self._s = s
        self._old_node = old_node
        self._new_node = new_node
        self._room_no = room_no

    @property
    def c(self) -> int:
        return self._c

    @property
    def s(self) -> int:
        return self._s

    @property
    def old_node(self) -> int:
        return self._old_node

    @property
    def new_node(self) -> int:
        return self._new_node

    @property
    def room_no(self) -> int:
        return self._room_no

    def _fields(self) -> tuple:
        return (self._c, self._s, self._old_node, self._new_node, self._room_no)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Move):
            return NotImplemented
        return self._fields() == other._fields()

    def __hash__(self) -> int:
        # hash() ตรงนี้ใช้เก็บ Move ลง set/dict เท่านั้น ไม่เกี่ยวกับตำแหน่งบนวงแหวน (วงแหวนใช้ hash64)
        return hash(self._fields())

    def __repr__(self) -> str:
        return (f"Move(c={self._c!r}, s={self._s!r}, old_node={self._old_node!r}, "
                f"new_node={self._new_node!r}, room_no={self._room_no!r})")


class MigrationReport:
    """ผลของการเพิ่ม/ลบอาคาร 1 ครั้ง

    moves เก็บเป็น tuple: ข้างนอกเพิ่มหรือลบรายการย้ายไม่ได้
    moved_count จึงเท่ากับจำนวนรายการย้ายที่พิมพ์/ส่งออกจริงเสมอ
    """

    __slots__ = ("_action", "_node_id", "_total_guests", "_moves")

    def __init__(self, action: str, node_id: int, total_guests: int, moves=()):
        if action not in ("add", "remove"):
            raise InvalidInputError(f"action ต้องเป็น 'add' หรือ 'remove' ไม่ใช่ {action!r}")
        self._action = action
        self._node_id = node_id
        self._total_guests = total_guests      # K ก่อนคำสั่ง
        self._moves = tuple(moves)             # สำเนา: แก้ list ต้นฉบับทีหลังไม่กระทบรายงาน

    @property
    def action(self) -> str:
        return self._action

    @property
    def node_id(self) -> int:
        return self._node_id

    @property
    def total_guests(self) -> int:
        return self._total_guests

    @property
    def moves(self) -> tuple:
        return self._moves

    @property
    def moved_count(self) -> int:
        return len(self._moves)

    @property
    def rate(self):
        if self._total_guests == 0:
            return None
        return self.moved_count / self._total_guests

    def describe(self) -> str:
        verb = "เพิ่ม" if self._action == "add" else "ลบ"
        text = (f"{verb}อาคาร {self._node_id}: แขกก่อนคำสั่ง {self._total_guests} คน "
                f"ย้าย {self.moved_count} คน")
        if self.rate is None:
            text += " (ไม่คำนวณอัตราเพราะไม่มีแขก)"
        else:
            text += f" (อัตราย้าย {self.rate:.4f} = {self.rate * 100:.2f}%)"
        return text

    def __repr__(self) -> str:
        return (f"MigrationReport(action={self._action!r}, node_id={self._node_id!r}, "
                f"total_guests={self._total_guests!r}, moved_count={self.moved_count})")


class LoadStats:
    """สถิติจำนวนแขกต่ออาคาร (รวมอาคารที่มี 0 คน)

    per_node คืนสำเนา dict ทุกครั้ง แก้ค่าที่ได้ไปก็ไม่กระทบสถิติต้นฉบับ
    cv เป็น None เมื่อไม่มีแขก (K = 0) เพราะหารด้วยศูนย์ไม่ได้
    """

    __slots__ = ("_per_node", "_max_load", "_min_load", "_mean", "_std", "_cv")

    def __init__(self, per_node: dict, max_load: int, min_load: int,
                 mean: float, std: float, cv):
        self._per_node = dict(per_node)
        self._max_load = max_load
        self._min_load = min_load
        self._mean = mean
        self._std = std
        self._cv = cv

    @property
    def per_node(self) -> dict:
        return dict(self._per_node)

    @property
    def max_load(self) -> int:
        return self._max_load

    @property
    def min_load(self) -> int:
        return self._min_load

    @property
    def mean(self) -> float:
        return self._mean

    @property
    def std(self) -> float:
        return self._std

    @property
    def cv(self):
        return self._cv

    def __repr__(self) -> str:
        return (f"LoadStats(per_node={self._per_node!r}, max_load={self._max_load!r}, "
                f"min_load={self._min_load!r}, mean={self._mean!r}, std={self._std!r}, cv={self._cv!r})")
