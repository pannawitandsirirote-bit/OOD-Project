from dataclasses import dataclass

from hotel.hashing import guest_key
from hotel.models import InvalidInputError


def room_number(c: int, s: int) -> int:
    if not isinstance(c, int) or not isinstance(s, int):
        raise InvalidInputError("c และ s ต้องเป็นจำนวนเต็ม")
    if c < 1 or s < 1:
        raise InvalidInputError("c และ s ต้องเป็นจำนวนเต็มบวก (c, s >= 1)")

    a = c - 1
    b = s - 1
    return ((a + b) * (a + b + 1)) // 2 + b + 1


@dataclass(frozen=True)
class Guest:
    c: int
    s: int
    room_no: int
    key: str

    @classmethod
    def create(cls, c: int, s: int) -> "Guest":
        return cls(c=c, s=s, room_no=room_number(c, s), key=guest_key(c, s))