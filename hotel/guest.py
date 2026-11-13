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
    __slots__ = ("__c", "__s", "__room_no", "__key")

    def __init__(self, c: int, s: int, room_no: int, key: str):
        self.__c = c
        self.__s = s
        self.__room_no = room_no
        self.__key = key

    @property
    def c(self) -> int:
        return self.__c

    @property
    def s(self) -> int:
        return self.__s

    @property
    def room_no(self) -> int:
        return self.__room_no

    @property
    def key(self) -> str:
        return self.__key

    @classmethod
    def create(cls, c: int, s: int) -> "Guest":
        return cls(c=c, s=s, room_no=room_number(c, s), key=guest_key(c, s))

    def __eq__(self, other) -> bool:
        if not isinstance(other, Guest):
            return NotImplemented
        return (self.__c, self.__s, self.__room_no, self.__key) == (
            other.__c, other.__s, other.__room_no, other.__key,
        )

    def __hash__(self) -> int:
        return hash((self.__c, self.__s, self.__room_no, self.__key))

    def __repr__(self) -> str:
        return (
            f"Guest(c={self.__c!r}, s={self.__s!r}, "
            f"room_no={self.__room_no!r}, key={self.__key!r})"
        )