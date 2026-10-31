# Distributed Hilbert's Hotel — Consistent Hashing

โครงงานรายวิชา **Object Oriented Data Structure (OODS)** ภาคการศึกษา 1/2569

โปรแกรม Python จัดแขกเข้าพักในเครือโรงแรมหลายอาคาร โดย **คำนวณ** ว่าแขกอยู่อาคารใดด้วย Consistent Hashing (วงแหวน 64 บิต + virtual node) และคำนวณเลขห้องจากรหัสแขกด้วย Cantor pairing function เมื่อเพิ่มหรือลบอาคาร แขกย้ายน้อยที่สุดและรายงานได้ว่าใครย้ายไปไหน พร้อมการทดลองเทียบกับวิธี `hash mod N`

---

## สารบัญ

1. [เริ่มต้นใช้งาน](#1-เริ่มต้นใช้งาน)
2. [โครงสร้างโปรเจกต์](#2-โครงสร้างโปรเจกต์)
3. [สมาชิกและการแบ่งงาน](#3-สมาชิกและการแบ่งงาน)
4. [ข้อตกลง Interface (ตกลงก่อนเริ่มเขียน)](#4-ข้อตกลง-interface-ตกลงก่อนเริ่มเขียน)
5. [กติกาหลักที่ห้ามพลาด](#5-กติกาหลักที่ห้ามพลาด)
6. [กรณีขอบ](#6-กรณีขอบ)
7. [การทดสอบ](#7-การทดสอบ)
8. [การทดลอง](#8-การทดลอง)
9. [การทำงานร่วมกันบน GitHub](#9-การทำงานร่วมกันบน-github)
10. [แผนงาน](#10-แผนงาน)
11. [การส่งงานและเช็กลิสต์](#11-การส่งงานและเช็กลิสต์)
12. [แหล่งอ้างอิง](#12-แหล่งอ้างอิง)

---

## 1. เริ่มต้นใช้งาน

| รายการ | ค่า |
|---|---|
| Python | **3.12** — ทุกคนใช้รุ่นเดียวกัน (ใส่รุ่นจริงจาก `python --version` ก่อนส่ง: `3.12.__`) |
| โปรแกรมหลัก | ใช้ไลบรารีมาตรฐานเท่านั้น (`hashlib`, `bisect`, `csv`, `time`, `tracemalloc`, `statistics`, `unittest`) |
| ไลบรารีเพิ่มเติม | `matplotlib` — ใช้วาดกราฟการทดลองเท่านั้น (อยู่ใน `requirements.txt`) |

```bash
# 1) clone และเตรียม environment
git clone https://github.com/pannawitandsirirote-bit/OOD-Project.git
cd OOD-Project
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2) รันโปรแกรม (เมนูข้อความ)
python main.py

# 3) รันทดสอบอัตโนมัติทั้งหมด
python -m unittest discover -s tests -v

# 4) รันการทดลอง A, B, C (salt 0, 1, 2) แล้ววาดกราฟ
python -m experiments.run_experiments --exp all --salts 0 1 2
python -m experiments.plot_results
```

> บน macOS/Linux บางเครื่องต้องใช้ `python3` แทน `python`

### เมนูของโปรแกรม (ครอบคลุมฟังก์ชันบังคับหัวข้อ 5)

| เมนู | การทำงาน |
|---|---|
| 1 | เริ่มระบบใหม่: จำนวนอาคาร N, ค่า V, จำนวนช่องทาง, จำนวนแขกของแต่ละช่องทาง |
| 2 | เพิ่มแขกรายคน `(c, s)` หรือเป็นกลุ่ม `(c, s_start, count)` |
| 3 | นำแขกออกด้วย `(c, s)` |
| 4 / 5 | เพิ่ม / ลบอาคาร พร้อมรายงานจำนวน อัตรา และรายการแขกที่ย้าย |
| 6 / 7 | ค้นหาด้วยรหัสแขก → `(node_id, room_no)` / ค้นหาด้วย `(node_id, room_no)` → รหัสแขก |
| 8 | แสดงรายการห้องที่มีผู้พัก (เรียง `node_id` แล้ว `room_no`) |
| 9 | รายงานความสมดุลของโหลด (ทุกอาคารรวมที่มี 0 คน, max, min, mean, SD, CV) |
| 10 | วัดเวลาและหน่วยความจำของฟังก์ชันหลัก |
| 11 | เปรียบเทียบ Consistent Hashing กับ `hash mod N` |
| 12 | ส่งออก CSV (แขก, รายการย้าย, ผลการทดลอง) |
| 0 | ออกจากโปรแกรม |

ข้อมูลจำนวนมากแสดงบนหน้าจอเพียงบางส่วนพร้อมบอกจำนวนทั้งหมด ส่วนไฟล์ CSV ต้องครบทุกแถว

---

## 2. โครงสร้างโปรเจกต์

```
OOD-Project/
├── README.md
├── requirements.txt
├── main.py                    # จุดเริ่มโปรแกรม → เรียก cli.menu
├── hotel/                     # ตรรกะหลัก (ห้ามมี print/input ในโฟลเดอร์นี้)
│   ├── __init__.py
│   ├── hashing.py             # hash64(), รูปแบบ key ของแขกและ virtual node
│   ├── guest.py               # Guest, room_number() (Cantor pairing)
│   ├── hash_ring.py           # HashRing — วงแหวน + virtual node + bisect
│   ├── mod_n.py               # ModNRouter — วิธีเทียบ hash mod N
│   ├── hotel_system.py        # HotelSystem — ข้อมูลแขก ดัชนี การย้าย สถิติ
│   ├── models.py              # Move, MigrationReport, LoadStats, ข้อผิดพลาด
│   └── csv_export.py          # ส่งออก CSV (UTF-8)
├── cli/
│   └── menu.py                # เมนูข้อความ รับ input และแสดงผลเท่านั้น
├── experiments/
│   ├── run_experiments.py     # การทดลอง A, B, C
│   ├── plot_results.py        # กราฟ (ก) (ข) (ค)
│   └── results/               # CSV ผลทดลอง + PNG กราฟ
├── tests/
│   ├── test_hashing.py
│   ├── test_guest.py
│   ├── test_hash_ring.py      # รวมตัวอย่างวงแหวนเล็กหัวข้อ 9.1
│   ├── test_hotel_system.py
│   ├── test_migration.py
│   ├── test_edge_cases.py
│   └── test_csv_export.py
├── data/                      # CSV ตัวอย่างสำหรับส่ง (แขก, รายการย้าย)
└── docs/
    ├── class_diagram.png
    └── report/                # รายงาน .docx และ .pdf
```

**หลักการ:** `hotel/` คือตรรกะล้วน ทดสอบได้โดยไม่ต้องผ่านเมนู ส่วน `cli/` แค่รับคำสั่ง เรียก `HotelSystem` และแสดงผล

---

## 3. สมาชิกและการแบ่งงาน

ทุกคนต้องเขียนโค้ด **และ** เขียนเทสต์ของส่วนตัวเอง และต้องอธิบายงานตัวเองกับกติกาหลักของระบบได้ตอนสาธิต

| # | ชื่อ – รหัสนักศึกษา | GitHub | ส่วนที่รับผิดชอบ | ไฟล์หลัก | เทสต์ |
|---|---|---|---|---|---|
| 1 | _ชื่อ_ | `@pannawitandsirirote-bit` | วงแหวนและการเลือกอาคาร: hash 64 บิต, virtual node, ค้นหาด้วย bisect, จุดชนกัน, วนกลับต้นวงแหวน | `hashing.py`, `hash_ring.py` | `test_hashing.py`, `test_hash_ring.py` |
| 2 | _ชื่อ_ | `@____` | ข้อมูลแขกและเลขห้อง: Cantor pairing, เพิ่ม/นำแขกออก (รายคน/กลุ่ม), ค้นหาสองทาง, รายการห้อง, สถิติโหลด | `guest.py`, `hotel_system.py` (ส่วนแขก) | `test_guest.py`, `test_hotel_system.py` |
| 3 | _ชื่อ_ | `@____` | เพิ่ม/ลบอาคารและการย้าย: MigrationReport, `hash mod N`, กรณีขอบ, ส่งออก CSV | `hotel_system.py` (ส่วนอาคาร), `mod_n.py`, `models.py`, `csv_export.py` | `test_migration.py`, `test_edge_cases.py`, `test_csv_export.py` |
| 4 | _ชื่อ_ | `@____` | การทดลองและส่วนติดต่อผู้ใช้: การทดลอง A/B/C, จับเวลา, tracemalloc, กราฟ, เมนูข้อความ | `experiments/`, `cli/menu.py`, `main.py` | smoke test ของเมนู, ตรวจ CSV ผลทดลอง |

**รายงาน:** ทุกคนเขียนส่วน "โครงสร้างข้อมูล + Big-O" ของงานตัวเอง คนที่ 4 เขียนส่วนการทดลอง บรรณาธิการรวมเล่ม: _กำหนด_ (ต้องใส่สัดส่วน % งานและลายเซ็นทุกคนในรายงาน)

---

## 4. ข้อตกลง Interface (ตกลงก่อนเริ่มเขียน)

ส่วนนี้คือ "สัญญา" ระหว่างสมาชิก ใครจะเปลี่ยนชื่อฟังก์ชันหรือชนิดข้อมูลต้องเปิด PR แก้ README ส่วนนี้และให้ทุกคนรับทราบก่อน

### ชนิดข้อมูลร่วม

- `node_id` เป็น `int` บวก ไม่ซ้ำ และไม่เปลี่ยนตามจำนวนอาคาร (เริ่มระบบสร้างอาคาร `1..N`)
- รหัสแขกเป็น `(c, s)` จำนวนเต็มบวก — `c` คือช่องทาง, `s` คือลำดับในช่องทาง (เริ่มที่ 1)
- ที่อยู่ห้องเป็น `(node_id, room_no)`

### `hotel/hashing.py`

```python
RING_SIZE = 2 ** 64

def guest_key(c: int, s: int) -> str: ...           # "guest:{c}:{s}"
def vnode_key(node_id: int, j: int) -> str: ...     # "node:{node_id}:{j}"  (j = 0..V-1)

def hash64(key: str, salt: str = "") -> int:
    """SHA-256 → 8 ไบต์แรก → int แบบ big-endian (0 .. 2^64-1)
    text = key ถ้า salt == "" มิฉะนั้น f"{salt}|{key}"
    เข้ารหัสข้อความเป็น UTF-8"""
```

### `hotel/guest.py`

```python
def room_number(c: int, s: int) -> int:
    """a = c-1, b = s-1 ; ((a+b)*(a+b+1))//2 + b + 1  — จำนวนเต็มล้วน ห้ามใช้ทศนิยม"""

@dataclass(frozen=True)
class Guest:
    c: int
    s: int
    room_no: int    # = room_number(c, s)
    key: str        # = guest_key(c, s)
```

### Router: `HashRing` และ `ModNRouter` (duck typing — ใช้แทนกันได้ใน HotelSystem)

```python
class HashRing:
    def __init__(self, v: int, salt: str = "", hash_fn=hash64): ...
    def add_node(self, node_id: int) -> None      # เพิ่มเฉพาะ V จุดของอาคารใหม่
    def remove_node(self, node_id: int) -> None   # ลบ V จุดของอาคารนั้นทั้งหมด
    def locate(self, position: int) -> int        # node_id ของจุดแรกที่ pos >= position (ไม่มีให้วนกลับ)
    def node_for(self, c: int, s: int) -> int     # locate(hash_fn(guest_key(c, s), salt))
    def nodes(self) -> list[int]                  # เรียงจากน้อยไปมาก
    def __len__(self) -> int                      # M = N × V
    # ภายใน: _points: list[tuple[pos, node_id, j]] เรียงตามคีย์ (pos, node_id, j)
    #        _positions: list[int] ขนานกับ _points ใช้กับ bisect_left

class ModNRouter:
    def __init__(self, salt: str = "", hash_fn=hash64): ...
    # _node_list: list[int] ตามลำดับที่เพิ่ม ; เพิ่ม = ต่อท้าย ; ลบ = เอาออกโดยรักษาลำดับที่เหลือ
    # node_for(c, s) = _node_list[hash_fn(guest_key(c, s), salt) % N]
    # มีเมธอด add_node / remove_node / node_for / nodes เหมือน HashRing
```

`hash_fn` ส่งเข้ามาได้เพื่อให้เทสต์กำหนดตำแหน่งเองได้ (เช่นวงแหวนขนาด 100 ในหัวข้อ 9.1)

### `hotel/hotel_system.py`

```python
class HotelSystem:
    def __init__(self, router): ...

    @classmethod
    def create(cls, n_nodes: int, v: int, guests_per_channel: list[int],
               salt: str = "", method: str = "ring") -> "HotelSystem": ...
        # method = "ring" | "modn" ; ช่องทาง c = 1..len(list) ; แต่ละช่อง s = 1..count

    # แขก
    def add_guest(self, c: int, s: int) -> Guest
    def add_guests(self, c: int, s_start: int, count: int) -> list[Guest]  # ซ้ำแม้ 1 คน → ปฏิเสธทั้งกลุ่ม
    def remove_guest(self, c: int, s: int) -> Guest

    # ค้นหา (ไม่พบคืน None — UI แสดง "ไม่พบ")
    def find_by_guest(self, c: int, s: int) -> tuple[int, int] | None    # (node_id, room_no)
    def find_by_room(self, node_id: int, room_no: int) -> tuple[int, int] | None  # (c, s)
    def compute_node(self, c: int, s: int) -> int    # คำนวณจาก router ตรง ๆ ไม่ใช้ค่าที่เก็บไว้

    # อาคาร
    def add_node(self, node_id: int) -> MigrationReport
    def remove_node(self, node_id: int) -> MigrationReport

    # รายงาน
    def list_rooms(self) -> list[tuple[int, int, int, int]]   # (node_id, room_no, c, s) เรียงแล้ว
    def load_stats(self) -> LoadStats
    @property
    def guest_count(self) -> int                               # K
```

**โครงสร้างข้อมูลภายใน (ต้องสอดคล้องกันตลอด):**

| ตัวแปร | ชนิด | ใช้ทำอะไร |
|---|---|---|
| `_location` | `dict[(c, s) → node_id]` | ค้นหาด้วยรหัสแขก / ตรวจรหัสซ้ำ O(1) |
| `_room_index` | `dict[(node_id, room_no) → (c, s)]` | ค้นหาด้วยที่อยู่ห้อง O(1) |
| `_load` | `dict[node_id → int]` | นับแขกต่ออาคาร (มีทุกอาคาร รวมที่เป็น 0) |

เมื่อแขกย้ายอาคาร ต้องอัปเดตทั้ง 3 ชุด (`room_no` คงเดิม เปลี่ยนเฉพาะ `node_id`) และเทสต์ต้องตรวจว่า `len(_location) == len(_room_index) == sum(_load.values())`

### `hotel/models.py`

```python
class HotelError(Exception): ...          # แม่ของข้อผิดพลาดที่ต้อง "ปฏิเสธอย่างสุภาพ"
class DuplicateNodeError(HotelError): ...
class NodeNotFoundError(HotelError): ...
class LastNodeError(HotelError): ...
class DuplicateGuestError(HotelError): ...
class GuestNotFoundError(HotelError): ...
class InvalidInputError(HotelError): ...  # ค่าติดลบ, ไม่ใช่จำนวนเต็ม, V < 1 ฯลฯ

@dataclass(frozen=True)
class Move:
    c: int; s: int; old_node: int; new_node: int; room_no: int

@dataclass
class MigrationReport:
    action: str              # "add" | "remove"
    node_id: int
    total_guests: int        # K ก่อนคำสั่ง
    moves: list[Move]
    moved_count -> int       # property = len(moves) เสมอ
    rate -> float | None     # property = moved_count / K ; None เมื่อ K == 0

@dataclass
class LoadStats:
    per_node: dict[int, int]
    max_load: int; min_load: int; mean: float; std: float
    cv: float | None         # std / mean ; None เมื่อ K == 0
```

**ข้อตกลงการจัดการข้อผิดพลาด:** ฟังก์ชันใน `hotel/` ตรวจความถูกต้อง **ทั้งหมดก่อน** แล้วจึงแก้ข้อมูล ถ้าผิดให้ `raise` ข้อผิดพลาดตระกูล `HotelError` (ข้อมูลเดิมจึงไม่เปลี่ยน) ส่วน `cli/` จับ `HotelError` แล้วแสดงข้อความ โปรแกรมต้องไม่หยุดทำงาน

### รูปแบบ CSV (UTF-8, เปิดไฟล์ด้วย `newline=""`)

| ไฟล์ | คอลัมน์ |
|---|---|
| `guests.csv` | `channel_id, sequence_id, node_id, room_no` |
| `moves.csv` | `channel_id, sequence_id, old_node_id, new_node_id, room_no` |
| `experiment_*.csv` | `experiment, salt, method, K, N, V, metric, value, unit` |

---

## 5. กติกาหลักที่ห้ามพลาด

- **แฮช:** ใช้ `hash64()` (SHA-256 ตัด 64 บิต) เท่านั้น **ห้ามใช้ `hash()` ของ Python** เพราะค่าไม่คงที่ข้ามการรัน
- **ห้ามใช้ไลบรารี Consistent Hashing สำเร็จรูป** — ใช้ได้แค่ `list`, `dict`, `set`, `hashlib`, `bisect` แล้วเขียนตรรกะวงแหวน การเลือกอาคาร และการย้ายเอง
- **การเลือกอาคาร:** หาจุดแรกที่ตำแหน่ง `>=` ตำแหน่งแขก ถ้าไม่มีให้วนกลับจุดแรกของวงแหวน
- **จุดชนกัน:** เก็บไว้ทุกจุด เรียงด้วย `(pos, node_id, j)` แล้วใช้ `bisect_left` จะได้จุดแรกตามลำดับนี้พอดี
- **เลขห้อง:** คำนวณจาก `(c, s)` ด้วย Cantor pairing เท่านั้น **ห้ามใช้ "เลขห้องล่าสุด + 1"** แขกที่แฮชตรงกันยังได้เลขห้องต่างกัน

  | `(c, s)` | (1,1) | (2,1) | (1,2) | (3,1) | (2,2) |
  |---|---|---|---|---|---|
  | `room_no` | 1 | 2 | 3 | 4 | 5 |

  เหตุผลที่ไม่ซ้ำ: Cantor pairing เป็นฟังก์ชันหนึ่งต่อหนึ่งทั่วถึงจาก ℕ₀×ℕ₀ ไป ℕ₀ และ `a = c−1, b = s−1` เป็นการแปลงหนึ่งต่อหนึ่ง การ `+1` แค่เลื่อนให้เป็นจำนวนเต็มบวก
- **เพิ่ม/ลบอาคาร:** แตะเฉพาะ V จุดของอาคารนั้น ห้ามเปลี่ยนตำแหน่งจุดที่เหลือ และห้ามเปลี่ยน V ระหว่างรอบ
- **ผลที่ถูกต้อง:** เพิ่มอาคาร → แขกที่ย้ายต้องย้าย **เข้าอาคารใหม่เท่านั้น** / ลบอาคาร → แขกในอาคารอื่น **ต้องไม่ย้าย**
- **นับการย้าย:** จำนวนรหัสแขกที่ `node_id` ก่อนและหลังต่างกัน (คนละ 1 ครั้ง) ไม่ใช่จำนวน virtual node ที่เปลี่ยน
- **อัตราการย้าย:** `moved / K` ถ้า K = 0 ให้รายงานย้าย 0 คนและแจ้งว่าไม่คำนวณอัตรา
- **การหาแขกที่ต้องย้าย:** ทำ **แบบ ก (ตรวจทุกคน)** ให้ผ่านเทสต์ก่อน แบบ ข (เฉพาะช่วงที่กระทบ) เป็นงานเสริม — Big-O ในรายงานต้องเป็นของแบบที่ใช้จริง

---

## 6. กรณีขอบ

ทุกกรณีต้องแจ้งเหตุผล คงข้อมูลเดิม และโปรแกรมไม่หยุดทำงาน

| กรณี | ผลที่ต้องได้ |
|---|---|
| เพิ่มรหัสอาคารที่มีอยู่แล้ว | `DuplicateNodeError` วงแหวนไม่เปลี่ยน |
| ลบรหัสอาคารที่ไม่มีอยู่ | `NodeNotFoundError` ไม่รายงานจำนวนคนย้าย |
| ลบอาคารสุดท้าย (แม้ไม่มีแขก) | `LastNodeError` เพราะต้องมี N ≥ 1 |
| เพิ่มรหัสแขกซ้ำ | `DuplicateGuestError` ไม่เขียนทับคนเดิม |
| เพิ่มกลุ่มที่ซ้ำแม้บางรายการ | ปฏิเสธ **ทั้งกลุ่ม** ข้อมูลเดิมไม่เปลี่ยน |
| เพิ่มกลุ่มจำนวน 0 | ไม่เปลี่ยนข้อมูล (ไม่ใช่ข้อผิดพลาด) |
| จำนวนติดลบ / ไม่ใช่จำนวนเต็ม / `c` หรือ `s` < 1 | `InvalidInputError` |
| นำแขกที่ไม่มีอยู่ออก | `GuestNotFoundError` K ไม่ลดลง |
| ค้นหาแล้วไม่พบ | คืน `None` แล้วเมนูแสดง "ไม่พบ" |
| ยังไม่มีแขก (K = 0) | สถิติพื้นฐานเป็น 0, `cv = None`, `rate = None` (ไม่หารด้วยศูนย์) |
| นำแขกออกแล้วเพิ่มรหัสเดิมกลับ | ถือเป็นการเข้าพักใหม่ คำนวณจากวงแหวนปัจจุบัน |

---

## 7. การทดสอบ

```bash
python -m unittest discover -s tests -v          # ทั้งหมด
python -m unittest tests.test_hash_ring -v       # เฉพาะไฟล์
```

ต้องผ่านทั้งหมดก่อน merge เข้า `main` และต้องส่งผลผ่าน/ไม่ผ่านพร้อมคำอธิบายกรณีที่ยังไม่ผ่าน (ภาพหน้าจออย่างเดียวไม่นับ)

### รายการทดสอบขั้นต่ำ (หัวข้อ 9.2)

- [ ] เพิ่มแขกใหม่ทั้งช่องทางเดิมและช่องทางใหม่ → ที่อยู่ห้องของแขกเดิมไม่เปลี่ยนแม้แต่คนเดียว
- [ ] เลขห้องตรงตามตารางตัวอย่าง และรหัสต่างกันไม่ได้ที่อยู่ห้องซ้ำกัน
- [ ] ปฏิเสธรหัสซ้ำ รวมกรณีเพิ่มเป็นกลุ่มที่ซ้ำเพียงบางรายการ และข้อมูลเดิมไม่เปลี่ยน
- [ ] ค้นหาที่ตำแหน่งตรงจุดอาคารพอดี ระหว่างจุด หลังจุดสุดท้าย (วนกลับ) และกรณี virtual node ชนกัน (ข้อมูลจำลอง)
- [ ] เพิ่มและลบอาคารเมื่อ V > 1 → ผู้ย้ายเป็นไปตามกติกา จำนวนแขกรวมไม่หายไม่เพิ่ม จำนวนรายการย้าย = ยอดที่รายงาน
- [ ] กรณีขอบในหัวข้อ 6 ทั้งหมด และจำนวนแถวใน CSV = จำนวนแขกปัจจุบัน

### ตัวอย่างวงแหวนเล็ก (หัวข้อ 9.1)

วงแหวนขนาด 100, V = 1 กำหนดตำแหน่งเองผ่าน `hash_fn` จำลอง: A(=1) ที่ 20, B(=2) ที่ 50, C(=3) ที่ 80 แต่ละกรณีเริ่มจากสถานะ A B C ใหม่

| ตำแหน่งแขก | เริ่มต้น A B C | เพิ่ม D(=4) ที่ 35 | ลบ B |
|---|---|---|---|
| 10 | A | A | A |
| 20 | A | A | A |
| 25 | B | **D** | **C** |
| 35 | B | **D** | **C** |
| 50 | B | B | **C** |
| 70 | C | C | C |
| 90 | A (วนกลับ) | A | A |

คาดหวัง: เพิ่ม D → ย้าย **2** คน, ลบ B → ย้าย **3** คน และเลขห้องของผู้ย้ายทุกคนคงเดิม

---

## 8. การทดลอง

| ชุด | ค่าที่เปลี่ยน | ค่าคงที่ | สิ่งที่วัด |
|---|---|---|---|
| A | K = 1,000 / 10,000 / 100,000 | N = 10, V = 32 | เวลาจัดแขก ค้นหา เรียงลำดับ และหน่วยความจำ |
| B | N = 5 / 10 / 20 | K = 10,000, V = 32 | เพิ่ม 1 และลบ 1 อาคาร: จำนวนย้าย อัตราย้าย เวลา — **เทียบกับ hash mod N** |
| C | V = 1 / 8 / 32 | N = 10, K = 10,000 | แขกต่ออาคาร, CV, หน่วยความจำ, การย้าย |

**ข้อกำหนดที่ต้องทำตาม**

- แขกมาจาก **10 ช่องทาง** จำนวนใกล้เคียงกัน
- ทำการทดลองละ **3 รอบ** ด้วย salt `"0"`, `"1"`, `"2"` และใช้ salt เดียวกันกับทั้งสองวิธีในรอบเดียวกัน
- ใช้รหัสแขก รหัสอาคาร และค่าแฮชชุดเดียวกันในแต่ละคู่เปรียบเทียบ ใช้เครื่องและ Python รุ่นเดียวกันตลอด
- `hash mod N` เทียบการย้ายด้วย **รหัสอาคารจริง** ไม่ใช่ดัชนี

**วิธีวัด**

- **เวลา:** `time.perf_counter()` แยกเวลาสร้างวงแหวน / จัดแขก / ค้นหา / เรียงลำดับ / เพิ่ม-ลบอาคาร ไม่รวมเวลารับแป้นพิมพ์ แสดงผล และเขียนไฟล์ ค้นหาวัดเป็นชุด 1,000 ครั้งแล้วหารต่อครั้ง รายงาน **มัธยฐานของ 3 รอบ**
- **หน่วยความจำ:** `tracemalloc` วัดส่วนที่เพิ่มจากจุดเริ่มเดียวกัน รายงาน current และ peak เป็น MiB (เป็นหน่วยความจำที่ Python ติดตาม ไม่ใช่ของทั้งโปรเซส) และ **แยกรอบวัดหน่วยความจำออกจากรอบจับเวลา**
- **ความสมดุล:** CV = ส่วนเบี่ยงเบนมาตรฐาน / ค่าเฉลี่ย (ทีมใช้ population SD — `statistics.pstdev`)

**ผลลัพธ์** อยู่ใน `experiments/results/` — CSV ทุกรอบพร้อมพารามิเตอร์และ salt และกราฟอย่างน้อย 3 ภาพ:

- (ก) เวลาเทียบ K
- (ข) อัตราการย้ายเทียบ N ของทั้งสองวิธี
- (ค) ผลของ V ต่อ CV และหน่วยความจำ

ทุกกราฟต้องมีชื่อแกน หน่วย พารามิเตอร์ และแสดงความแปรปรวน 3 รอบ (ค่าเฉลี่ยกับช่วงต่ำสุด–สูงสุด)

---

## 9. การทำงานร่วมกันบน GitHub

### Branch

- `main` — โค้ดที่ผ่านเทสต์แล้วเท่านั้น ห้าม push ตรง ต้องผ่าน Pull Request เสมอ
- `feat/<ส่วนงาน>` เช่น `feat/hash-ring`, `feat/guest`, `feat/migration`, `feat/experiments`, `feat/cli`
- `fix/<เรื่อง>` สำหรับแก้บั๊ก

```bash
git checkout main && git pull
git checkout -b feat/hash-ring
# ... เขียนโค้ด + เทสต์ ...
python -m unittest discover -s tests -v
git add . && git commit -m "feat(ring): add bisect lookup with wrap-around"
git push -u origin feat/hash-ring
# เปิด Pull Request บน GitHub → เช็กตามรายการด้านล่าง → merge → แจ้งทีมให้ git pull
```

### Commit message

`<type>(<scope>): <สรุปสั้น ๆ>` — type ที่ใช้: `feat`, `fix`, `test`, `docs`, `exp` (การทดลอง), `refactor`

### Pull Request

- 1 PR = 1 เรื่อง ไม่ใหญ่เกินไป
- ต้องมีเทสต์ของสิ่งที่เพิ่ม และเทสต์ทั้งหมดต้องผ่าน
- เจ้าของ PR merge เองได้ (ตกลงในทีมแล้ว) ถ้า PR แก้ไฟล์ของคนอื่นหรือแก้ Interface หัวข้อ 4 ให้บอกเจ้าของไฟล์และทีมก่อน merge
- ก่อน merge เช็ก: ตรงกับ Interface หัวข้อ 4, ไม่มี `print`/`input` ใน `hotel/`, ไม่ใช้ `hash()` ของ Python, กรณีขอบไม่ทำให้ข้อมูลเปลี่ยน
- หลัง merge แจ้งทีมในกลุ่มให้ `git pull`
- ใช้ GitHub Issues จดงานย่อยและบั๊ก ติด label ตามส่วนงาน (`ring`, `guest`, `migration`, `experiment`, `cli`, `report`)

### `.gitignore` ขั้นต่ำ

```
.venv/
__pycache__/
*.pyc
.DS_Store
~$*.docx
```

---

## 10. แผนงาน

กำหนดส่งจริงจะประกาศภายหลัง ใส่วันที่เมื่อทราบ

| ระยะ | งาน | เสร็จเมื่อ |
|---|---|---|
| 0 | สร้าง repo, ตกลง Interface หัวข้อ 4, สร้างไฟล์โครง (stub) ทุกไฟล์ | ทุกคน import ไฟล์ของกันและกันได้ |
| 1 | `hash64`, `HashRing`, `Guest`, `HotelSystem` (ส่วนแขก + ค้นหา) พร้อมเทสต์ | ผ่านเทสต์วงแหวนเล็ก 9.1 และเทสต์เลขห้อง |
| 2 | เพิ่ม/ลบอาคาร + `MigrationReport`, `ModNRouter`, กรณีขอบ, CSV, เมนูข้อความ | ผ่านรายการทดสอบขั้นต่ำครบ |
| 3 | การทดลอง A/B/C × 3 salt, กราฟ (ก)(ข)(ค) | มี CSV + PNG ครบใน `experiments/results/` |
| 4 | รายงาน (Big-O ตรงกับโค้ดจริง), แผนภาพคลาส, ซ้อมสาธิต, ทำ ZIP | ผ่านเช็กลิสต์หัวข้อ 11 |
| เสริม | แบบ ข (หาเฉพาะช่วงที่กระทบ), วาดภาพวงแหวน, อ่านข้อมูลกลับจากไฟล์ | ทำหลังงานบังคับผ่านเทสต์แล้วเท่านั้น |

---

## 11. การส่งงานและเช็กลิสต์

### สิ่งที่ต้องส่งผ่าน MS Teams (ZIP ชุดเดียว เปิดแล้วเจอ README ทันที)

1. โค้ด Python ทั้งหมด + `main.py` + สคริปต์ทดสอบ + README นี้
2. รายงาน Word และ PDF เนื้อหาตรงกัน
3. CSV: ข้อมูลแขกตัวอย่าง, รายการย้าย, ข้อมูลผลทดลองพร้อมพารามิเตอร์และ salt
4. ตารางหน้าที่สมาชิก (ใส่ในรายงานได้) พร้อม % งานและลายเซ็น

```bash
# สร้าง ZIP จากไฟล์ที่ commit แล้วเท่านั้น (ไม่ติด .venv)
git archive --format=zip -o OODS_HilbertHotel_<ชื่อกลุ่ม>.zip HEAD
```

ห้ามแนบ virtual environment หรือแพ็กเกจที่ติดตั้งไว้

### เช็กลิสต์ก่อนส่ง (หัวข้อ 12)

- [ ] เพิ่มแขกใหม่แล้ว ที่อยู่ห้องของแขกเดิมไม่เปลี่ยนแม้แต่คนเดียว
- [ ] เลขห้องคำนวณจากรหัสแขกล้วน ๆ ไม่มีที่ไหนใช้ "เลขล่าสุด + 1"
- [ ] เพิ่มอาคารแล้วผู้ย้ายเข้าอาคารใหม่เท่านั้น ลบอาคารแล้วแขกอาคารอื่นไม่ขยับ
- [ ] จำนวนที่รายงานว่าย้าย = จำนวนรายการย้ายที่พิมพ์ออกมาจริง
- [ ] ปิดแล้วเปิดโปรแกรมใหม่ ค่าแฮชยังเหมือนเดิม (ไม่ได้ใช้ `hash()` ของ Python)
- [ ] กรณีขอบทั้งหมดไม่ทำให้โปรแกรมหยุดทำงาน
- [ ] จำนวนแถวใน CSV = จำนวนแขกในระบบ
- [ ] กราฟทุกภาพมีชื่อแกน หน่วย และพารามิเตอร์กำกับ
- [ ] Big-O ในรายงานตรงกับโค้ดที่ส่งจริง ระบุกรณี (เลวร้ายสุด/เฉลี่ย/คาดหวัง) และสมมติฐานขนาดรหัสคงที่
- [ ] README ระบุรุ่น Python จริง วิธีเรียกโปรแกรม และวิธีรันทดสอบ

---

## 12. แหล่งอ้างอิง

- Hilbert's Hotel: https://youtu.be/HLTjDXT9SqQ
- Consistent Hashing (ByteByteGo): https://www.youtube.com/watch?v=UF9Iqmg94tk
- Python `bisect`: https://docs.python.org/3/library/bisect.html
- Python `tracemalloc`: https://docs.python.org/3/library/tracemalloc.html
- Python `time.perf_counter`: https://docs.python.org/3/library/time.html#time.perf_counter
