"""จุดเริ่มโปรแกรม: python main.py"""
import sys

from cli.menu import Menu


def main() -> None:
    try:  # ให้พิมพ์ภาษาไทยได้บน terminal ที่ไม่ใช่ UTF-8 (เช่น Windows รุ่นเก่า)
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    Menu().run()


if __name__ == "__main__":
    main()
