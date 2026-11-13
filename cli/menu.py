"""เมนูข้อความของ Distributed Hilbert's Hotel

หน้าที่ของไฟล์นี้: รับ input -> เรียก HotelSystem -> แสดงผล เท่านั้น
ตรรกะวงแหวน เลขห้อง และการย้ายอยู่ในแพ็กเกจ hotel/ ทั้งหมด

หลักการจัดการข้อผิดพลาด (ตามข้อตกลงใน README หัวข้อ 4):
  * hotel/ ตรวจก่อนแก้ข้อมูลและ raise HotelError  -> เมนูจับแล้วแจ้ง "ปฏิเสธ" ข้อมูลเดิมไม่เปลี่ยน
  * input ที่พิมพ์ผิดรูปแบบ (ไม่ใช่ตัวเลข ฯลฯ)     -> BadInput แจ้งแล้วกลับเมนูหลัก
  * โปรแกรมต้องไม่หยุดทำงานเพราะกรณีเหล่านี้
"""
from __future__ import annotations

from pathlib import Path

from experiments import run_experiments as exp
from experiments.results_io import RESULT_COLUMNS, make_row, write_rows
from hotel.hotel_system import HotelSystem
from hotel.models import HotelError

MAX_GUESTS = 1_000_000      # กันพิมพ์เลขใหญ่เกินจนเครื่องค้าง
SHOW_DEFAULT = 20           # จำนวนแถวที่แสดงโดยปริยาย
MOVE_LINES_LIMIT = 50       # รายการย้ายเกินนี้ถามก่อนว่าจะแสดงทั้งหมดหรือไม่
DATA_DIR = Path("data")

MENU_TEXT = """
==================== Distributed Hilbert's Hotel ====================
 1  เริ่มระบบใหม่ (N, V, ช่องทาง, จำนวนแขก)    7  ค้นด้วย (node_id, room_no)
 2  เพิ่มแขก (รายคน / เป็นกลุ่ม)               8  แสดงรายการห้องที่มีผู้พัก
 3  นำแขกออก                                   9  รายงานความสมดุลของโหลด
 4  เพิ่มอาคาร                                10  วัดเวลา + หน่วยความจำ
 5  ลบอาคาร                                   11  เทียบ Consistent Hashing กับ hash mod N
 6  ค้นด้วยรหัสแขก (c, s)                     12  ส่งออก CSV
 0  ออกจากโปรแกรม
======================================================================"""

TIMING_LABELS = {
    "build_ring_s": "สร้างวงแหวน",
    "place_guests_s": "จัดแขก (ทั้งชุด)",
    "search_by_guest_per_call_s": "ค้นด้วยรหัสแขก (ต่อครั้ง)",
    "search_by_room_per_call_s": "ค้นด้วยที่อยู่ห้อง (ต่อครั้ง)",
    "compute_node_per_call_s": "คำนวณอาคารจากวงแหวน (ต่อครั้ง)",
    "sort_rooms_s": "เรียงรายการห้อง",
    "mem_current_mib": "หน่วยความจำ current",
    "mem_peak_mib": "หน่วยความจำ peak",
}


class BadInput(Exception):
    """สิ่งที่ผู้ใช้พิมพ์ไม่ถูกต้อง (ไม่ใช่ข้อผิดพลาดของระบบโรงแรม)"""


class Menu:
    def __init__(self, input_fn=input, print_fn=print, data_dir=DATA_DIR):
        self.__input = input_fn
        self.__print = print_fn
        self.__data_dir = Path(data_dir)
        self.__system: HotelSystem | None = None
        self.__last_report = None
        self.__last_experiment_rows: list[dict] = []
        self.__actions = {
            "1": self.__init_system, "2": self.__add_guest, "3": self.__remove_guest,
            "4": self.__add_node, "5": self.__remove_node, "6": self.__find_by_guest,
            "7": self.__find_by_room, "8": self.__list_rooms, "9": self.__load_report,
            "10": self.__measure, "11": self.__compare, "12": self.__export,
        }

    @property
    def system(self) -> HotelSystem | None:
        """ระบบโรงแรมที่ใช้งานอยู่ (อ่านอย่างเดียว) เป็น None ถ้ายังไม่ได้เริ่มระบบ"""
        return self.__system

    # ------------------------------------------------------------------ วงรอบหลัก
    def run(self) -> None:
        while True:
            self.__print(MENU_TEXT)
            try:
                choice = self.__ask("เลือกเมนู: ")
            except (EOFError, KeyboardInterrupt):
                self.__print("\nจบการทำงาน")
                return
            if choice == "0":
                self.__print("ออกจากโปรแกรม")
                return
            action = self.__actions.get(choice)
            if action is None:
                self.__print(f"[!] ไม่มีเมนู '{choice}' กรุณาเลือก 0-12")
                continue
            try:
                action()
            except KeyboardInterrupt:
                self.__print("\n[!] ยกเลิกคำสั่งนี้")
            except EOFError:
                self.__print("\nจบการทำงาน (ไม่มี input เพิ่ม)")
                return
            except BadInput as e:
                self.__print(f"[!] ข้อมูลไม่ถูกต้อง: {e}")
            except HotelError as e:
                self.__print(f"[!] ปฏิเสธ: {e} (ข้อมูลเดิมไม่เปลี่ยน)")
            except OSError as e:
                self.__print(f"[!] เขียน/อ่านไฟล์ไม่ได้: {e}")
            except Exception as e:  # ด่านสุดท้าย: เมนูต้องไม่ล้ม แต่แจ้งให้เห็นว่าเป็นบั๊ก
                self.__print(f"[!] เกิดข้อผิดพลาดที่ไม่คาดคิด ({type(e).__name__}): {e}")

    # ------------------------------------------------------------------ ตัวช่วยรับ input
    def __ask(self, prompt: str) -> str:
        return self.__input(prompt).strip()

    def __ask_int(self, prompt: str, minimum: int | None = None, default: int | None = None,
                 maximum: int | None = None) -> int:
        text = self.__ask(prompt)
        if text == "" and default is not None:
            return default
        try:
            value = int(text)
        except ValueError:
            raise BadInput(f"'{text}' ไม่ใช่จำนวนเต็ม") from None
        if minimum is not None and value < minimum:
            raise BadInput(f"ต้องเป็นจำนวนเต็มตั้งแต่ {minimum} ขึ้นไป (ได้ {value})")
        if maximum is not None and value > maximum:
            raise BadInput(f"ค่ามากเกินไป: ไม่เกิน {maximum:,} (ได้ {value:,})")
        return value

    def __confirm(self, prompt: str) -> bool:
        return self.__ask(prompt + " (y/N): ").lower() in ("y", "yes", "ใช่")

    def __need_system(self) -> HotelSystem:
        if self.__system is None:
            raise BadInput("ยังไม่ได้เริ่มระบบ กรุณาเลือกเมนู 1 ก่อน")
        return self.__system

    def __node_ids(self) -> list[int]:
        return sorted(self.__need_system().load_stats().per_node)

    def __ask_path(self, default: Path) -> Path:
        text = self.__ask(f"ชื่อไฟล์ [Enter = {default}]: ")
        return Path(text) if text else default

    # ------------------------------------------------------------------ 1 เริ่มระบบ
    def __init_system(self) -> None:
        n = self.__ask_int("จำนวนอาคาร N (>= 1): ", minimum=1)
        v = self.__ask_int("virtual node ต่ออาคาร V (>= 1) [Enter = 32]: ", minimum=1, default=32)
        channels = self.__ask_int("จำนวนช่องทาง (>= 0) [Enter = 10]: ", minimum=0, default=10)
        counts = self.__ask_counts(channels)
        salt = self.__ask("salt [Enter = ไม่ใช้]: ")
        system = HotelSystem.create(n, v, counts, salt=salt, method="ring")
        self.__system = system  # เปลี่ยนระบบเมื่อสร้างสำเร็จเท่านั้น
        self.__last_report = None
        self.__print(f"เริ่มระบบแล้ว: N={n}, V={v}, ช่องทาง={channels}, แขกทั้งหมด K = {system.guest_count}")

    def __ask_counts(self, channels: int) -> list[int]:
        if channels == 0:
            return []
        text = self.__ask(f"จำนวนแขกต่อช่องทาง (ตัวเลขเดียว = ใช้ทุกช่อง หรือพิมพ์ {channels} ตัวคั่นด้วยเว้นวรรค): ")
        tokens = text.split()
        if not tokens:
            raise BadInput("ยังไม่ได้ใส่จำนวนแขก")
        try:
            numbers = [int(t) for t in tokens]
        except ValueError:
            raise BadInput(f"'{text}' มีค่าที่ไม่ใช่จำนวนเต็ม") from None
        if len(numbers) == 1:
            numbers = numbers * channels
        elif len(numbers) != channels:
            raise BadInput(f"ต้องใส่ 1 ค่า หรือ {channels} ค่า (ได้ {len(numbers)} ค่า)")
        if any(x < 0 for x in numbers):
            raise BadInput("จำนวนแขกต้องไม่ติดลบ")
        if sum(numbers) > MAX_GUESTS:
            raise BadInput(f"จำนวนแขกรวมมากเกินไป: ไม่เกิน {MAX_GUESTS:,}")
        return numbers

    # ------------------------------------------------------------------ 2-3 แขก
    def __add_guest(self) -> None:
        system = self.__need_system()
        mode = self.__ask("1) รายคน  2) เป็นกลุ่ม : ")
        if mode == "1":
            c = self.__ask_int("ช่องทาง c (>= 1): ", minimum=1)
            s = self.__ask_int("ลำดับ s (>= 1): ", minimum=1)
            guest = system.add_guest(c, s)
            node_id, _ = system.find_by_guest(c, s)
            self.__print(f"เพิ่มแขก ({c}, {s}) -> อาคาร {node_id}, ห้อง {guest.room_no} | K = {system.guest_count}")
        elif mode == "2":
            c = self.__ask_int("ช่องทาง c (>= 1): ", minimum=1)
            s_start = self.__ask_int("ลำดับเริ่มต้น s_start (>= 1): ", minimum=1)
            count = self.__ask_int("จำนวนแขก (>= 0): ", minimum=0, maximum=MAX_GUESTS)
            guests = system.add_guests(c, s_start, count)
            if count == 0:
                self.__print(f"จำนวน 0 -> ไม่เปลี่ยนข้อมูล | K = {system.guest_count}")
            else:
                self.__print(f"เพิ่มแขกช่องทาง {c} ลำดับ {s_start}..{s_start + count - 1} "
                            f"จำนวน {len(guests)} คน | K = {system.guest_count}")
        else:
            raise BadInput("เลือก 1 หรือ 2")

    def __remove_guest(self) -> None:
        system = self.__need_system()
        c = self.__ask_int("ช่องทาง c (>= 1): ", minimum=1)
        s = self.__ask_int("ลำดับ s (>= 1): ", minimum=1)
        system.remove_guest(c, s)
        self.__print(f"นำแขก ({c}, {s}) ออกแล้ว | K = {system.guest_count}")

    # ------------------------------------------------------------------ 4-5 อาคาร
    def __add_node(self) -> None:
        system = self.__need_system()
        suggested = max(self.__node_ids()) + 1
        node_id = self.__ask_int(f"รหัสอาคารใหม่ (>= 1) [Enter = {suggested}]: ", minimum=1, default=suggested)
        report = system.add_node(node_id)
        self.__last_report = report
        self.__show_report(report)

    def __remove_node(self) -> None:
        system = self.__need_system()
        ids = self.__node_ids()
        self.__print(f"อาคารที่มีอยู่: {', '.join(map(str, ids))}")
        node_id = self.__ask_int("รหัสอาคารที่จะลบ: ", minimum=1)
        report = system.remove_node(node_id)
        self.__last_report = report
        self.__show_report(report)

    def __show_report(self, report) -> None:
        verb = "เพิ่ม" if report.action == "add" else "ลบ"
        self.__print(f"=== {verb}อาคาร {report.node_id} ===")
        self.__print(f"แขกก่อนคำสั่ง K = {report.total_guests}")
        self.__print(f"จำนวนแขกที่ย้าย = {report.moved_count}")
        if report.rate is None:
            self.__print("อัตราการย้าย: ไม่คำนวณ เพราะไม่มีแขก (K = 0)")
        else:
            self.__print(f"อัตราการย้าย = {report.moved_count}/{report.total_guests} "
                        f"= {report.rate:.4f} ({report.rate * 100:.2f}%)")
        moves = report.moves
        if not moves:
            return
        limit = len(moves)
        if len(moves) > MOVE_LINES_LIMIT and not self.__confirm(
                f"มีรายการย้าย {len(moves)} รายการ แสดงทั้งหมดหรือไม่ (ไม่ = แสดง {MOVE_LINES_LIMIT} รายการแรก)"):
            limit = MOVE_LINES_LIMIT
        self.__print(f"{'รหัสแขก (c, s)':<18}{'อาคารเดิม':>10}{'อาคารใหม่':>10}{'ห้อง':>14}")
        for m in moves[:limit]:
            self.__print(f"{f'({m.c}, {m.s})':<18}{m.old_node:>10}{m.new_node:>10}{m.room_no:>14}")
        self.__print(f"แสดง {limit} จากรายการย้ายทั้งหมด {len(moves)} รายการ"
                    + ("" if limit == len(moves) else " (ส่งออกครบด้วยเมนู 12 -> 2)"))

    # ------------------------------------------------------------------ 6-7 ค้นหา
    def __find_by_guest(self) -> None:
        system = self.__need_system()
        c = self.__ask_int("ช่องทาง c (>= 1): ", minimum=1)
        s = self.__ask_int("ลำดับ s (>= 1): ", minimum=1)
        found = system.find_by_guest(c, s)
        if found is None:
            self.__print(f"ไม่พบแขก ({c}, {s}) ในระบบ")
        else:
            node_id, room_no = found
            self.__print(f"แขก ({c}, {s}) -> อาคาร {node_id}, ห้อง {room_no}")

    def __find_by_room(self) -> None:
        system = self.__need_system()
        node_id = self.__ask_int("รหัสอาคาร node_id (>= 1): ", minimum=1)
        room_no = self.__ask_int("หมายเลขห้อง room_no (>= 1): ", minimum=1)
        found = system.find_by_room(node_id, room_no)
        if found is None:
            self.__print(f"ไม่พบผู้พักที่อาคาร {node_id} ห้อง {room_no}")
        else:
            c, s = found
            self.__print(f"อาคาร {node_id} ห้อง {room_no} -> แขก ({c}, {s})")

    # ------------------------------------------------------------------ 8-9 รายงาน
    def __list_rooms(self) -> None:
        system = self.__need_system()
        rows = system.list_rooms()
        if not rows:
            self.__print("ยังไม่มีผู้พัก (K = 0)")
            return
        limit = self.__ask_int(f"จำนวนแถวที่จะแสดง [Enter = {SHOW_DEFAULT}, 0 = ทั้งหมด]: ",
                              minimum=0, default=SHOW_DEFAULT)
        shown = rows if limit == 0 else rows[:limit]
        self.__print(f"{'node_id':>8}{'room_no':>14}   แขก (c, s)")
        for node_id, room_no, c, s in shown:
            self.__print(f"{node_id:>8}{room_no:>14}   ({c}, {s})")
        self.__print(f"แสดง {len(shown)} จากผู้พักทั้งหมด {len(rows)} ห้อง")

    def __load_report(self) -> None:
        stats = self.__need_system().load_stats()
        total = sum(stats.per_node.values())
        self.__print(f"แขกทั้งหมด K = {total} | อาคาร {len(stats.per_node)} หลัง")
        for node_id in sorted(stats.per_node):
            self.__print(f"  อาคาร {node_id:>3}: {stats.per_node[node_id]} คน")
        self.__print(f"สูงสุด = {stats.max_load} | ต่ำสุด = {stats.min_load} | "
                    f"เฉลี่ย = {stats.mean:.2f} | SD = {stats.std:.2f}")
        if stats.cv is None:
            self.__print("CV: ไม่คำนวณ เพราะไม่มีแขก (K = 0)")
        else:
            self.__print(f"CV = SD / เฉลี่ย = {stats.cv:.4f} (ยิ่งต่ำยิ่งสมดุล)")

    # ------------------------------------------------------------------ 10-11 ทดลอง
    def __ask_experiment_params(self, minimum_n: int = 1) -> tuple[int, int, int, str]:
        k = self.__ask_int("จำนวนแขก K [Enter = 10000]: ", minimum=1, default=10_000, maximum=MAX_GUESTS)
        n = self.__ask_int("จำนวนอาคาร N [Enter = 10]: ", minimum=minimum_n, default=10)
        v = self.__ask_int("virtual node V [Enter = 32]: ", minimum=1, default=32)
        salt = self.__ask("salt [Enter = 0]: ") or "0"
        return k, n, v, salt

    def __measure(self) -> None:
        k, n, v, salt = self.__ask_experiment_params()
        self.__print(f"กำลังวัด... (Consistent Hashing, K={k:,}, N={n}, V={v}, salt={salt!r}, 10 ช่องทาง)")
        self.__print("หมายเหตุ: วัดบนระบบทดลองแยกต่างหาก ไม่กระทบระบบที่กำลังใช้งานอยู่")
        measured = exp.measure_timing("ring", n, v, k, salt)           # รอบจับเวลา
        measured.update(exp.measure_memory("ring", n, v, k, salt))     # รอบวัดหน่วยความจำ (แยกกัน)
        self.__print(f"{'รายการ':<36}{'ค่า':>14}  หน่วย")
        rows = []
        for metric, value in measured.items():
            unit = "s" if metric.endswith("_s") else "MiB"
            shown = f"{value:.6g}"
            self.__print(f"{TIMING_LABELS.get(metric, metric):<36}{shown:>14}  {unit}")
            rows.append(make_row("menu10", salt, "ring", k, n, v, metric, value))
        self.__print("หน่วยความจำ = ส่วนที่ Python ติดตามด้วย tracemalloc ไม่ใช่ของทั้งโปรเซส | วัด 1 รอบ (ชุดเต็ม 3 รอบ ใช้ experiments.run_experiments)")
        self.__last_experiment_rows = rows

    def __compare(self) -> None:
        k, n, v, salt = self.__ask_experiment_params(minimum_n=2)
        self.__print(f"กำลังเทียบ... (K={k:,}, N={n}, V={v}, salt={salt!r}) ชุดแขกและ salt เดียวกันทั้งสองวิธี")
        results = {method: exp.measure_migration(method, n, v, k, salt) for method in exp.METHODS}
        header = f"{'วิธี':<8}{'เพิ่ม: ย้าย':>13}{'อัตรา':>9}{'เวลา(s)':>11}{'ลบ: ย้าย':>12}{'อัตรา':>9}{'เวลา(s)':>11}"
        self.__print(header)
        rows = []
        for method, r in results.items():
            self.__print(f"{method:<8}{r['add_moved']:>13}{r['add_move_rate']:>9.4f}{r['add_time_s']:>11.6f}"
                        f"{r['remove_moved']:>12}{r['remove_move_rate']:>9.4f}{r['remove_time_s']:>11.6f}")
            for metric, value in r.items():
                rows.append(make_row("menu11", salt, method, k, n, v, metric, value))
        self.__print(f"ค่าคาดหวัง Consistent Hashing: เพิ่ม ~ K/(N+1) = {k / (n + 1):.1f} คน, ลบ ~ K/N = {k / n:.1f} คน "
                    "(เป็นค่าคาดหวัง ผลจริงอาจต่าง)")
        self.__last_experiment_rows = rows

    # ------------------------------------------------------------------ 12 ส่งออก CSV
    def __export(self) -> None:
        self.__print("ส่งออก: 1) แขกทั้งหมด  2) รายการย้ายล่าสุด  3) ผลวัด/เทียบจากเมนู 10-11")
        choice = self.__ask("เลือก: ")
        if choice == "1":
            system = self.__need_system()
            path = self.__ask_path(self.__data_dir / "guests.csv")
            rooms = system.list_rooms()
            rows = [{"channel_id": c, "sequence_id": s, "node_id": node_id, "room_no": room_no}
                    for node_id, room_no, c, s in rooms]
            written = write_rows(path, rows, ["channel_id", "sequence_id", "node_id", "room_no"])
            verdict = "ตรงกับจำนวนแขกในระบบ" if written == system.guest_count else "ไม่ตรงกับจำนวนแขกในระบบ!"
            self.__print(f"เขียน {written} แถว -> {path} (K = {system.guest_count}: {verdict})")
        elif choice == "2":
            if self.__last_report is None:
                raise BadInput("ยังไม่มีรายการย้าย กรุณาเพิ่ม/ลบอาคาร (เมนู 4 หรือ 5) ก่อน")
            path = self.__ask_path(self.__data_dir / "moves.csv")
            rows = [{"channel_id": m.c, "sequence_id": m.s, "old_node_id": m.old_node,
                     "new_node_id": m.new_node, "room_no": m.room_no} for m in self.__last_report.moves]
            written = write_rows(path, rows, ["channel_id", "sequence_id", "old_node_id", "new_node_id", "room_no"])
            self.__print(f"เขียน {written} แถว -> {path} (รายงานว่าย้าย {self.__last_report.moved_count} คน)")
        elif choice == "3":
            if not self.__last_experiment_rows:
                raise BadInput("ยังไม่มีผลวัด กรุณารันเมนู 10 หรือ 11 ก่อน")
            path = self.__ask_path(self.__data_dir / "experiment_menu.csv")
            written = write_rows(path, self.__last_experiment_rows, RESULT_COLUMNS)
            self.__print(f"เขียน {written} แถว -> {path}")
        else:
            raise BadInput("เลือก 1, 2 หรือ 3")
