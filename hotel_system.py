import statistics
from typing import Optional

from hotel.guest import Guest, room_number
from hotel.models import (
    DuplicateGuestError,
    DuplicateNodeError,
    GuestNotFoundError,
    InvalidInputError,
    LastNodeError,
    LoadStats,
    MigrationReport,
    Move,
    NodeNotFoundError,
)


class HotelSystem:
    def __init__(self, router):
        self._router = router
        self._location = {} 
        self._room_index = {}
        self._load = {node_id: 0 for node_id in router.nodes()}

    @classmethod
    def create(cls, n_nodes: int, v: int, guests_per_channel: list,
               salt: str = "", method: str = "ring") -> "HotelSystem":
        if not isinstance(n_nodes, int) or n_nodes < 1:
            raise InvalidInputError("n_nodes ต้องเป็นจำนวนเต็มบวก")
        if not isinstance(v, int) or v < 1:
            raise InvalidInputError("v ต้องเป็นจำนวนเต็ม >= 1")

        if method == "ring":
            from hotel.hash_ring import HashRing
            router = HashRing(v=v, salt=salt)
        elif method == "modn":
            from hotel.mod_n import ModNRouter
            router = ModNRouter(salt=salt)
        else:
            raise InvalidInputError("method ต้องเป็น 'ring' หรือ 'modn'")

        for node_id in range(1, n_nodes + 1):
            router.add_node(node_id)

        system = cls(router)
        for idx, count in enumerate(guests_per_channel, start=1):
            if count:
                system.add_guests(idx, 1, count)
        return system

    def add_guest(self, c: int, s: int) -> Guest:
        self._validate_guest_code(c, s)
        key = (c, s)
        if key in self._location:
            raise DuplicateGuestError(f"รหัสแขก {key} มีอยู่แล้ว")

        guest = Guest.create(c, s)
        node_id = self._router.node_for(c, s)

        self._location[key] = node_id
        self._room_index[(node_id, guest.room_no)] = key
        self._load[node_id] = self._load.get(node_id, 0) + 1
        return guest

    def add_guests(self, c: int, s_start: int, count: int) -> list:
        if not isinstance(count, int) or count < 0:
            raise InvalidInputError("count ต้องเป็นจำนวนเต็มไม่ติดลบ")
        if count == 0:
            return []

        self._validate_guest_code(c, s_start)
        codes = [(c, s_start + i) for i in range(count)]

        duplicates = [code for code in codes if code in self._location]
        if duplicates:
            raise DuplicateGuestError(
                f"รหัสแขกซ้ำในกลุ่มที่จะเพิ่ม: {duplicates} — ปฏิเสธทั้งกลุ่ม"
            )

        return [self.add_guest(cc, ss) for cc, ss in codes]

    def remove_guest(self, c: int, s: int) -> Guest:
        self._validate_guest_code(c, s)
        key = (c, s)
        if key not in self._location:
            raise GuestNotFoundError(f"ไม่พบรหัสแขก {key}")

        node_id = self._location.pop(key)
        room_no = room_number(c, s)
        del self._room_index[(node_id, room_no)]
        self._load[node_id] -= 1

        return Guest.create(c, s)

    def find_by_guest(self, c: int, s: int) -> Optional[tuple]:
        node_id = self._location.get((c, s))
        if node_id is None:
            return None
        return (node_id, room_number(c, s))

    def find_by_room(self, node_id: int, room_no: int) -> Optional[tuple]:
        return self._room_index.get((node_id, room_no))

    def compute_node(self, c: int, s: int) -> int:
        """คำนวณจาก router ตรง ๆ ไม่ใช้ค่าที่เก็บไว้ใน _location"""
        return self._router.node_for(c, s)

    def list_rooms(self) -> list:
        rows = [
            (node_id, room_no, code[0], code[1])
            for (node_id, room_no), code in self._room_index.items()
        ]
        rows.sort(key=lambda row: (row[0], row[1]))
        return rows

    def load_stats(self) -> LoadStats:
        per_node = dict(self._load)
        loads = list(per_node.values())

        if self.guest_count == 0:
            max_load = max(loads) if loads else 0
            min_load = min(loads) if loads else 0
            return LoadStats(per_node=per_node, max_load=max_load, min_load=min_load,
                              mean=0.0, std=0.0, cv=None)

        mean = statistics.mean(loads)
        std = statistics.pstdev(loads)
        cv = (std / mean) if mean > 0 else None
        return LoadStats(per_node=per_node, max_load=max(loads), min_load=min(loads),
                          mean=mean, std=std, cv=cv)

    @property
    def guest_count(self) -> int:
        return len(self._location)

    @staticmethod
    def _validate_guest_code(c, s):
        if not isinstance(c, int) or not isinstance(s, int):
            raise InvalidInputError("c และ s ต้องเป็นจำนวนเต็ม")
        if c < 1 or s < 1:
            raise InvalidInputError("c และ s ต้องเป็นจำนวนเต็มบวก (c, s >= 1)")

    #building

    def add_node(self, node_id: int) -> MigrationReport:
        if not isinstance(node_id, int):
            raise InvalidInputError("node_id ต้องเป็นจำนวนเต็ม")
        if node_id in self._router.nodes():
            raise DuplicateNodeError(f"อาคาร {node_id} มีอยู่แล้ว")

        total = self.guest_count
        self._router.add_node(node_id)
        self._load[node_id] = 0

        moves = []
        for (c, s), old_node in list(self._location.items()):
            new_node = self._router.node_for(c, s)
            if new_node != old_node:
                room_no = room_number(c, s)
                self._location[(c, s)] = new_node
                del self._room_index[(old_node, room_no)]
                self._room_index[(new_node, room_no)] = (c, s)
                self._load[old_node] -= 1
                self._load[new_node] += 1
                moves.append(Move(c=c, s=s, old_node=old_node, new_node=new_node, room_no=room_no))

        return MigrationReport(action="add", node_id=node_id, total_guests=total, moves=moves)

    def remove_node(self, node_id: int) -> MigrationReport:
        if node_id not in self._router.nodes():
            raise NodeNotFoundError(f"ไม่พบอาคาร {node_id}")
        if len(self._router.nodes()) <= 1:
            raise LastNodeError("ต้องมีอาคารอย่างน้อย 1 แห่งเสมอ")

        total = self.guest_count
        self._router.remove_node(node_id)

        moves = []
        for (c, s), old_node in list(self._location.items()):
            if old_node != node_id:
                continue
            new_node = self._router.node_for(c, s)
            room_no = room_number(c, s)
            self._location[(c, s)] = new_node
            del self._room_index[(node_id, room_no)]
            self._room_index[(new_node, room_no)] = (c, s)
            self._load[new_node] = self._load.get(new_node, 0) + 1
            moves.append(Move(c=c, s=s, old_node=node_id, new_node=new_node, room_no=room_no))

        del self._load[node_id]

        return MigrationReport(action="remove", node_id=node_id, total_guests=total, moves=moves)