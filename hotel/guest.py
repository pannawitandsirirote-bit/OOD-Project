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


class Guest:
    __slots__ = ("_c", "_s", "_room_no", "_key")

    def __init__(self, c: int, s: int, room_no: int, key: str):
        self._c = c
        self._s = s
        self._room_no = room_no
        self._key = key

    @property
    def c(self) -> int:
        return self._c

    @property
    def s(self) -> int:
        return self._s

    @property
    def room_no(self) -> int:
        return self._room_no

    @property
    def key(self) -> str:
        return self._key

    @classmethod
    def create(cls, c: int, s: int) -> "Guest":
        return cls(c=c, s=s, room_no=room_number(c, s), key=guest_key(c, s))

    def __eq__(self, other) -> bool:
        if not isinstance(other, Guest):
            return NotImplemented
        return (self._c, self._s, self._room_no, self._key) == (
            other._c, other._s, other._room_no, other._key,
        )

    def __hash__(self) -> int:
        return hash((self._c, self._s, self._room_no, self._key))

    def __repr__(self) -> str:
        return (
            f"Guest(c={self._c!r}, s={self._s!r}, "
            f"room_no={self._room_no!r}, key={self._key!r})"
        )