from .hashing import guest_key, hash64
from .models import DuplicateNodeError, InvalidInputError, NodeNotFoundError


class ModNRouter:
    def __init__(self, salt: str = "", hash_fn=hash64):
        self.__salt = salt
        self.__hash_fn = hash_fn
        self.__node_list = []      

    def add_node(self, node_id: int) -> None:
        if node_id in self.__node_list:                       
            raise DuplicateNodeError(f"อาคาร {node_id} มีอยู่แล้ว")
        self.__node_list.append(node_id)                    

    def remove_node(self, node_id: int) -> None:
        if node_id not in self.__node_list:
            raise NodeNotFoundError(f"ไม่พบอาคาร {node_id}")
        self.__node_list.remove(node_id)                      

    def node_for(self, c: int, s: int) -> int:
        if not self.__node_list:
            raise InvalidInputError("ไม่มีอาคารในระบบ")
        h = self.__hash_fn(guest_key(c, s), self.__salt)
        return self.__node_list[h % len(self.__node_list)]   

    def nodes(self) -> list:
        return sorted(self.__node_list)

    def __len__(self) -> int:
        return len(self.__node_list)                          
