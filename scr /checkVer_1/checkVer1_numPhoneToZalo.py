#!/usr/bin/env python3
"""
Zalo Phone Checker — Kiểm tra SĐT có đăng ký Zalo không
=========================================================
Dùng thư viện `zlapi` (unofficial) để lookup SĐT từ file CSV.

Cách dùng:
  python checkVer1_numPhoneToZalo.py input.csv --imei YOUR_IMEI --cookies cookies.json
  python checkVer1_numPhoneToZalo.py input.csv -o results.csv -d 1.5

Lấy IMEI & cookies:
  1. Mở Zalo Web (web.zalo.me) trên Chrome → F12 → Application → Local Storage
  2. Tìm key "z_uuid" hoặc "zalo_data" → copy IMEI
  3. Dùng EditThisCookie extension → Export cookies → lưu thành cookies.json

Lưu ý:
  - Đây là thư viện UNOFFICIAL → tài khoản có thể bị khóa nếu dùng quá mức
  - Zalo không cung cấp API công khai cho việc này
  - Nên dùng tài khoản phụ và delay >= 1s
"""

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ─── Kiểm tra thư viện ───────────────────────────────────────────────────────

try:
    from zlapi import ZaloAPI
    from zlapi.models import *
    ZLAPI_AVAILABLE = True
except ImportError:
    ZLAPI_AVAILABLE = False

# ─── Màu terminal ────────────────────────────────────────────────────────────

class C:
    GREEN  = "\033[92m"
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    GRAY   = "\033[90m"
    WHITE  = "\033[97m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"

def supports_color() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

USE_COLOR = supports_color()

def c(color: str, text: str) -> str:
    return f"{color}{text}{C.RESET}" if USE_COLOR else text

# ─── Data class ──────────────────────────────────────────────────────────────

@dataclass
class ZaloResult:
    customer_name: str
    phone:         str
    has_zalo:      str = "unknown"   # "yes" | "no" | "unknown"
    zalo_name:     str = ""
    zalo_id:       str = ""
    gender:        str = ""
    avatar:        str = ""
    note:          str = ""
    checked_at:    str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))

# ─── Normalize SĐT ───────────────────────────────────────────────────────────

def normalize_phone(raw: str) -> str:
    """
    Chuẩn hóa SĐT về dạng 10 số hoặc +84...
    VD: 0896140216 / 84896140216 / +84896140216 / 896140216 → 0896140216
    """
    phone = raw.strip().replace(" ", "").replace("-", "").replace(".", "")
    # Loại bỏ dấu +
    if phone.startswith("+84"):
        phone = "0" + phone[3:]
    elif phone.startswith("84") and len(phone) == 11:
        phone = "0" + phone[2:]
    # Nếu chỉ có 9 số (thiếu đầu 0)
    if len(phone) == 9 and not phone.startswith("0"):
        phone = "0" + phone
    return phone

def is_valid_phone(phone: str) -> bool:
    return phone.isdigit() and len(phone) in (10, 11)

# ─── Core check ──────────────────────────────────────────────────────────────

def check_phone_zalo(client: "ZaloAPI", customer_name: str, raw_phone: str) -> ZaloResult:
    phone = normalize_phone(raw_phone)

    if not is_valid_phone(phone):
        return ZaloResult(
            customer_name=customer_name,
            phone=raw_phone,
            has_zalo="unknown",
            note=f"SĐT không hợp lệ: '{raw_phone}'"
        )

    try:
        result = client.fetchPhoneNumber(phone, language="vi")

        # result là object/dict tùy phiên bản zlapi
        if result is None:
            return ZaloResult(
                customer_name=customer_name,
                phone=phone,
                has_zalo="no",
                note="Không tìm thấy tài khoản Zalo"
            )

        # Xử lý response dạng dict hoặc object
        data = result if isinstance(result, dict) else vars(result)

        # Trường hợp API trả về lỗi
        error_code = data.get("error_code") or data.get("errorCode")
        if error_code and int(error_code) != 0:
            error_msg = data.get("error_message") or data.get("errorMessage", "")
            return ZaloResult(
                customer_name=customer_name,
                phone=phone,
                has_zalo="no",
                note=f"Không có Zalo ({error_msg})"
            )

        # Lấy thông tin user
        display_name = (
            data.get("displayName")
            or data.get("display_name")
            or data.get("name")
            or ""
        )
        zalo_id = (
            data.get("userId")
            or data.get("user_id")
            or data.get("uid")
            or data.get("id")
            or ""
        )
        gender_raw = data.get("gender") or data.get("sex") or ""
        gender_map = {0: "Nữ", 1: "Nam", 2: "Khác", "0": "Nữ", "1": "Nam"}
        gender = gender_map.get(gender_raw, str(gender_raw))

        avatar = (
            data.get("avatar")
            or data.get("avatarUrl")
            or data.get("avatar_url")
            or ""
        )

        return ZaloResult(
            customer_name=customer_name,
            phone=phone,
            has_zalo="yes",
            zalo_name=str(display_name),
            zalo_id=str(zalo_id),
            gender=gender,
            avatar=str(avatar),
            note=""
        )

    except Exception as e:
        err = str(e)
        # zlapi trả về lỗi nếu không tìm thấy
        if any(kw in err.lower() for kw in ["not found", "no account", "không tìm", "error"]):
            return ZaloResult(
                customer_name=customer_name,
                phone=phone,
                has_zalo="no",
                note="Không có tài khoản Zalo"
            )
        return ZaloResult(
            customer_name=customer_name,
            phone=phone,
            has_zalo="unknown",
            note=f"Lỗi: {err[:80]}"
        )

# ─── Display ─────────────────────────────────────────────────────────────────

STATUS_ICON = {
    "yes":     lambda: c(C.GREEN,  "✓ CÓ ZALO "),
    "no":      lambda: c(C.RED,    "✗ KHÔNG   "),
    "unknown": lambda: c(C.YELLOW, "? UNKNOWN "),
}

def print_result(r: ZaloResult, idx: int, total: int):
    icon  = STATUS_ICON.get(r.has_zalo, STATUS_ICON["unknown"])()
    idx_s = c(C.GRAY, f"[{idx:>3}/{total}]")
    name_s = c(C.CYAN, f"[{r.customer_name[:15]}]") if r.customer_name else ""

    detail = ""
    if r.has_zalo == "yes":
        detail = c(C.GREEN, f" → {r.zalo_name}")
        if r.zalo_id:
            detail += c(C.GRAY, f" (ID: {r.zalo_id})")
        if r.gender:
            detail += c(C.GRAY, f" | {r.gender}")
    elif r.note:
        detail = c(C.GRAY, f" — {r.note}")

    print(f"{idx_s} {icon}  {name_s} {r.phone}{detail}")

def print_summary(results: list):
    yes     = sum(1 for r in results if r.has_zalo == "yes")
    no      = sum(1 for r in results if r.has_zalo == "no")
    unknown = sum(1 for r in results if r.has_zalo == "unknown")
    total   = len(results)

    print()
    print(c(C.BOLD, "─" * 65))
    print(c(C.BOLD, "  KẾT QUẢ TỔNG HỢP — ZALO PHONE CHECKER"))
    print(c(C.BOLD, "─" * 65))
    print(f"  Tổng SĐT kiểm tra   : {c(C.BOLD, str(total))}")
    print(f"  ✓ Có tài khoản Zalo : {c(C.GREEN, str(yes))}")
    print(f"  ✗ Không có Zalo     : {c(C.RED, str(no))}")
    print(f"  ? Không xác định    : {c(C.YELLOW, str(unknown))}")
    print(c(C.BOLD, "─" * 65))
    if total:
        print(f"  Tỉ lệ có Zalo       : {c(C.CYAN, f'{yes/total*100:.1f}%')}")
    print()

# ─── Export ──────────────────────────────────────────────────────────────────

def export_csv(results: list, path: str):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Tên KH", "SĐT", "Có Zalo?",
            "Tên Zalo", "Zalo ID", "Giới tính",
            "Avatar", "Ghi chú", "Giờ check"
        ])
        for r in results:
            writer.writerow([
                r.customer_name, r.phone, r.has_zalo,
                r.zalo_name, r.zalo_id, r.gender,
                r.avatar, r.note, r.checked_at
            ])
    print(c(C.GREEN, f"  → Đã xuất: {path}"))

# ─── Load CSV ────────────────────────────────────────────────────────────────

def load_csv(path: str) -> list:
    """
    Đọc file CSV, tự động tìm cột 'Tên KH' và 'SĐT'.
    Trả về list[(customer_name, phone)]
    """
    p = Path(path)
    if not p.exists():
        print(c(C.RED, f"[!] File không tồn tại: {path}"))
        sys.exit(1)

    data = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return []

        header_lower = [h.strip().lower() for h in header]

        # Tìm index cột
        name_idx  = next((i for i, h in enumerate(header_lower) if h in ("tên kh", "tên khách hàng", "name", "họ tên", "khách hàng")), 0)
        phone_idx = next((i for i, h in enumerate(header_lower) if h in ("sđt", "sdt", "điện thoại", "phone", "số điện thoại")), None)

        if phone_idx is None:
            print(c(C.RED, f"[!] Không tìm thấy cột SĐT trong file CSV!"))
            print(c(C.GRAY, f"    Các cột hiện có: {', '.join(header)}"))
            sys.exit(1)

        print(c(C.GRAY, f"  → Dùng cột: Tên KH=[{header[name_idx]}], SĐT=[{header[phone_idx]}]"))

        for row in reader:
            if not row or all(cell.strip() == "" for cell in row):
                continue
            name  = row[name_idx].strip()  if name_idx  < len(row) else ""
            phone = row[phone_idx].strip() if phone_idx < len(row) else ""
            if phone:
                data.append((name, phone))

    return data

# ─── Load cookies ────────────────────────────────────────────────────────────

def load_cookies(path: str) -> dict:
    """Đọc cookies từ file JSON (export từ EditThisCookie hoặc tương tự)"""
    p = Path(path)
    if not p.exists():
        print(c(C.RED, f"[!] File cookies không tồn tại: {path}"))
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Xử lý nhiều định dạng khác nhau
    if isinstance(raw, list):
        # EditThisCookie format: [{"name": "key", "value": "val", ...}]
        return {item["name"]: item["value"] for item in raw if "name" in item}
    elif isinstance(raw, dict):
        return raw
    return {}

# ─── Setup ───────────────────────────────────────────────────────────────────

def setup_instructions():
    """In hướng dẫn lấy IMEI và cookies"""
    print()
    print(c(C.BOLD,   "╔══════════════════════════════════════════════════════════════╗"))
    print(c(C.BOLD,   "║          HƯỚNG DẪN LẤY IMEI & COOKIES TỪ ZALO WEB          ║"))
    print(c(C.BOLD,   "╚══════════════════════════════════════════════════════════════╝"))
    print()
    print(c(C.CYAN,   "  Bước 1: Mở trình duyệt Chrome/Firefox"))
    print(c(C.WHITE,  "          → Truy cập: https://chat.zalo.me"))
    print(c(C.WHITE,  "          → Đăng nhập tài khoản Zalo của bạn"))
    print()
    print(c(C.CYAN,   "  Bước 2: Lấy IMEI (z_uuid)"))
    print(c(C.WHITE,  "          → Nhấn F12 → Tab 'Application' (Chrome) hoặc 'Storage' (Firefox)"))
    print(c(C.WHITE,  "          → Local Storage → https://chat.zalo.me"))
    print(c(C.WHITE,  "          → Tìm key 'z_uuid' → copy giá trị"))
    print()
    print(c(C.CYAN,   "  Bước 3: Lấy Cookies"))
    print(c(C.WHITE,  "          → Cài extension 'EditThisCookie' hoặc 'Cookie Editor'"))
    print(c(C.WHITE,  "          → Vào chat.zalo.me → Click icon extension → Export"))
    print(c(C.WHITE,  "          → Lưu thành file: cookies.json"))
    print()
    print(c(C.CYAN,   "  Bước 4: Chạy script"))
    print(c(C.WHITE,  "          python checkVer1_numPhoneToZalo.py input.csv \\"))
    print(c(C.WHITE,  "                 --imei YOUR_Z_UUID_HERE \\"))
    print(c(C.WHITE,  "                 --cookies cookies.json"))
    print()
    print(c(C.YELLOW, "  ⚠  Khuyến nghị: Dùng tài khoản phụ, delay >= 1.5s"))
    print(c(C.YELLOW, "  ⚠  Tài khoản có thể bị khóa nếu request quá nhiều"))
    print()

# ─── Args ────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Zalo Phone Checker — kiểm tra SĐT có đăng ký Zalo không",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python checkVer1_numPhoneToZalo.py input.csv --imei abc123 --cookies cookies.json
  python checkVer1_numPhoneToZalo.py input.csv --imei abc123 --cookies cookies.json -o results.csv -d 2
  python checkVer1_numPhoneToZalo.py --setup
        """
    )
    parser.add_argument("input",       nargs="?", help="File CSV chứa danh sách SĐT")
    parser.add_argument("--imei",      default="", help="IMEI / z_uuid lấy từ Zalo Web Local Storage")
    parser.add_argument("--cookies",   default="cookies.json", help="File JSON chứa cookies (mặc định: cookies.json)")
    parser.add_argument("--phone",     default="", help="Số điện thoại tài khoản Zalo đăng nhập")
    parser.add_argument("--password",  default="", help="Mật khẩu Zalo (nếu không dùng cookies)")
    parser.add_argument("-o", "--output", default="", help="Xuất kết quả ra file CSV")
    parser.add_argument("-d", "--delay",  type=float, default=1.5, help="Delay giữa mỗi request (giây, mặc định: 1.5)")
    parser.add_argument("--setup",     action="store_true", help="Hiển thị hướng dẫn lấy IMEI & cookies")
    return parser.parse_args()

# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    if args.setup or not args.input:
        setup_instructions()
        sys.exit(0)

    # Kiểm tra zlapi
    if not ZLAPI_AVAILABLE:
        print(c(C.RED, "\n[!] Thư viện 'zlapi' chưa được cài đặt."))
        print(c(C.YELLOW, "    Chạy lệnh sau để cài:\n"))
        print(c(C.CYAN,   "    pip install zlapi\n"))
        print(c(C.GRAY,   "    Hoặc bản mới nhất từ GitHub:"))
        print(c(C.CYAN,   "    pip install git+https://github.com/Its-VrxxDev/zlapi.git\n"))
        sys.exit(1)

    # Kiểm tra credentials
    if not args.imei:
        print(c(C.RED, "\n[!] Thiếu --imei. Chạy --setup để xem hướng dẫn.\n"))
        sys.exit(1)

    # Load cookies
    session_cookies = {}
    cookies_path = Path(args.cookies)
    if cookies_path.exists():
        session_cookies = load_cookies(args.cookies)
        print(c(C.GRAY, f"  → Đã load {len(session_cookies)} cookies từ {args.cookies}"))
    elif not args.phone:
        print(c(C.YELLOW, f"  [!] Không tìm thấy {args.cookies}. Thử đăng nhập qua --phone/--password"))

    # Load dữ liệu CSV
    data = load_csv(args.input)
    total = len(data)

    if not total:
        print(c(C.YELLOW, "[!] Không có SĐT nào để check."))
        sys.exit(0)

    # Khởi tạo ZaloAPI client
    print(c(C.GRAY, "\n  → Đang kết nối Zalo..."))
    try:
        client = ZaloAPI(
            phone=args.phone or "0000000000",
            password=args.password or "",
            imei=args.imei,
            session_cookies=session_cookies,
        )
    except Exception as e:
        print(c(C.RED, f"\n[!] Không thể khởi tạo ZaloAPI: {e}"))
        print(c(C.YELLOW, "    Kiểm tra lại IMEI và cookies."))
        sys.exit(1)

    # Header
    print()
    print(c(C.BOLD, f"  Zalo Phone Checker  —  {total} SĐT"))
    print(c(C.GRAY, f"  Delay: {args.delay}s  |  Input: {args.input}"))
    print(c(C.BOLD, "─" * 65))
    print()

    results = []

    for i, (name, phone) in enumerate(data, 1):
        r = check_phone_zalo(client, name, phone)
        results.append(r)
        print_result(r, i, total)

        # Delay để tránh bị rate-limit
        if i < total:
            time.sleep(args.delay)

    print_summary(results)

    # Xuất CSV
    out_path = args.output
    if not out_path:
        out_path = f"zalo_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    export_csv(results, out_path)


if __name__ == "__main__":
    main()
