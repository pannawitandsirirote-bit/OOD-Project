"""ชนิดข้อมูลร่วมของระบบ: ข้อผิดพลาด, รายการย้าย, รายงานการย้าย และสถิติโหลด

Move / MigrationReport / LoadStats เก็บค่าเป็นแอตทริบิวต์ private (ขึ้นต้นด้วย __ สองขีด)
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

    __slots__ = ("__c", "__s", "__old_node", "__new_node", "__room_no")

    def __init__(self, c: int, s: int, old_node: int, new_node: int, room_no: int):
        self.__c = c
        self.__s = s
        self.__old_node = old_node
        self.__new_node = new_node
        self.__room_no = room_no

    @property
    def c(self) -> int:
        return self.__c

    @property
    def s(self) -> int:
        return self.__s

    @property
    def old_node(self) -> int:
        return self.__old_node

    @property
    def new_node(self) -> int:
        return self.__new_node

    @property
    def room_no(self) -> int:
        return self.__room_no

    def __fields(self) -> tuple:
        return (self.__c, self.__s, self.__old_node, self.__new_node, self.__room_no)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Move):
            return NotImplemented
        return self.__fields() == other.__fields()

    def __hash__(self) -> int:
        # hash() ตรงนี้ใช้เก็บ Move ลง set/dict เท่านั้น ไม่เกี่ยวกับตำแหน่งบนวงแหวน (วงแหวนใช้ hash64)
        return hash(self.__fields())

    def __repr__(self) -> str:
        return (f"Move(c={self.__c!r}, s={self.__s!r}, old_node={self.__old_node!r}, "
                f"new_node={self.__new_node!r}, room_no={self.__room_no!r})")


class MigrationReport:
    """ผลของการเพิ่ม/ลบอาคาร 1 ครั้ง

    moves เก็บเป็น tuple: ข้างนอกเพิ่มหรือลบรายการย้ายไม่ได้
    moved_count จึงเท่ากับจำนวนรายการย้ายที่พิมพ์/ส่งออกจริงเสมอ
    """

    __slots__ = ("__action", "__node_id", "__total_guests", "__moves")

    def __init__(self, action: str, node_id: int, total_guests: int, moves=()):
        if action not in ("add", "remove"):
            raise InvalidInputError(f"action ต้องเป็น 'add' หรือ 'remove' ไม่ใช่ {action!r}")
        self.__action = action
        self.__node_id = node_id
        self.__total_guests = total_guests      # K ก่อนคำสั่ง
        self.__moves = tuple(moves)             # สำเนา: แก้ list ต้นฉบับทีหลังไม่กระทบรายงาน

    @property
    def action(self) -> str:
        return self.__action

    @property
    def node_id(self) -> int:
        return self.__node_id

    @property
    def total_guests(self) -> int:
        return self.__total_guests

    @property
    def moves(self) -> tuple:
        return self.__moves

    @property
    def moved_count(self) -> int:
        return len(self.__moves)

    @property
    def rate(self):
        if self.__total_guests == 0:
            return None
        return self.moved_count / self.__total_guests

    def describe(self) -> str:
        verb = "เพิ่ม" if self.__action == "add" else "ลบ"
        text = (f"{verb}อาคาร {self.__node_id}: แขกก่อนคำสั่ง {self.__total_guests} คน "
                f"ย้าย {self.moved_count} คน")
        if self.rate is None:
            text += " (ไม่คำนวณอัตราเพราะไม่มีแขก)"
        else:
            text += f" (อัตราย้าย {self.rate:.4f} = {self.rate * 100:.2f}%)"
        return text

    def __repr__(self) -> str:
        return (f"MigrationReport(action={self.__action!r}, node_id={self.__node_id!r}, "
                f"total_guests={self.__total_guests!r}, moved_count={self.moved_count})")


class LoadStats:
    """สถิติจำนวนแขกต่ออาคาร (รวมอาคารที่มี 0 คน)

    per_node คืนสำเนา dict ทุกครั้ง แก้ค่าที่ได้ไปก็ไม่กระทบสถิติต้นฉบับ
    cv เป็น None เมื่อไม่มีแขก (K = 0) เพราะหารด้วยศูนย์ไม่ได้
    """

    __slots__ = ("__per_node", "__max_load", "__min_load", "__mean", "__std", "__cv")

    def __init__(self, per_node: dict, max_load: int, min_load: int,
                 mean: float, std: float, cv):
        self.__per_node = dict(per_node)
        self.__max_load = max_load
        self.__min_load = min_load
        self.__mean = mean
        self.__std = std
        self.__cv = cv

    @property
    def per_node(self) -> dict:
        return dict(self.__per_node)

    @property
    def max_load(self) -> int:
        return self.__max_load

    @property
    def min_load(self) -> int:
        return self.__min_load

    @property
    def mean(self) -> float:
        return self.__mean

    @property
    def std(self) -> float:
        return self.__std

    @property
    def cv(self):
        return self.__cv

    def __repr__(self) -> str:
        return (f"LoadStats(per_node={self.__per_node!r}, max_load={self.__max_load!r}, "
                f"min_load={self.__min_load!r}, mean={self.__mean!r}, std={self.__std!r}, cv={self.__cv!r})")
