from dataclasses import dataclass, field


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


@dataclass(frozen=True)
class Move:
    """แขก 1 คนที่เปลี่ยนอาคาร (room_no คงเดิมเสมอ)"""
    c: int
    s: int
    old_node: int
    new_node: int
    room_no: int


@dataclass
class MigrationReport:
    action: str             
    node_id: int
    total_guests: int      
    moves: list = field(default_factory=list)   

    def __post_init__(self):
        if self.action not in ("add", "remove"):
            raise InvalidInputError(f"action ต้องเป็น 'add' หรือ 'remove' ไม่ใช่ {self.action!r}")

    @property
    def moved_count(self) -> int:
        return len(self.moves)

    @property
    def rate(self):
        if self.total_guests == 0:
            return None
        return self.moved_count / self.total_guests

    def describe(self) -> str:
        verb = "เพิ่ม" if self.action == "add" else "ลบ"
        text = (f"{verb}อาคาร {self.node_id}: แขกก่อนคำสั่ง {self.total_guests} คน "
                f"ย้าย {self.moved_count} คน")
        if self.rate is None:
            text += " (ไม่คำนวณอัตราเพราะไม่มีแขก)"
        else:
            text += f" (อัตราย้าย {self.rate:.4f} = {self.rate * 100:.2f}%)"
        return text


@dataclass
class LoadStats:
    per_node: dict        
    max_load: int
    min_load: int
    mean: float
    std: float               
    cv: object              
