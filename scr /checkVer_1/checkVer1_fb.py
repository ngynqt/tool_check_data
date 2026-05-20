#!/usr/bin/env python3
"""
FB Link Checker — HTTP HEAD request
Kiểm tra khả năng sống của link Facebook mà không cần đăng nhập.

Cách dùng:
  python checkVer1.py input.csv
  python checkVer1.py input.csv -o results.csv -t 10 -d 0.5 -w 5

input.csv: file CSV có 2 cột (Cột 1: Tên KH, Cột 2: Link FB)
"""

import argparse
import csv
import sys
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    print("[!] Thiếu thư viện. Chạy: pip install requests")
    sys.exit(1)

# ─── Màu terminal ────────────────────────────────────────────────────────────

class C:
    GREEN  = "\033[92m"
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    GRAY   = "\033[90m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"

def supports_color() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

USE_COLOR = supports_color()

def c(color: str, text: str) -> str:
    return f"{color}{text}{C.RESET}" if USE_COLOR else text

# ─── Cấu hình ────────────────────────────────────────────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/124.0.0.0 Safari/537.36",
]

# HTTP codes → trạng thái
STATUS_MAP = {
    200: ("alive",   "Còn sống"),
    301: ("alive",   "Còn sống (redirect)"),
    302: ("alive",   "Còn sống (redirect)"),
    303: ("alive",   "Còn sống (redirect)"),
    307: ("alive",   "Còn sống (redirect)"),
    308: ("alive",   "Còn sống (redirect)"),
    400: ("unknown", "Bad Request"),
    401: ("alive",   "Còn sống (cần đăng nhập)"),
    403: ("alive",   "Còn sống (bị chặn)"),
    404: ("dead",    "Không tồn tại"),
    410: ("dead",    "Đã bị xóa vĩnh viễn"),
    429: ("unknown", "Rate limit"),
    500: ("unknown", "Lỗi server"),
    502: ("unknown", "Bad Gateway"),
    503: ("unknown", "Server không phản hồi"),
}

# ─── Data ─────────────────────────────────────────────────────────────────────

@dataclass
class Result:
    customer_name: str
    url:        str
    status:     str = "unknown"   # alive | dead | unknown
    http_code:  Optional[int] = None
    note:       str = ""
    elapsed_ms: int = 0
    checked_at: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))

# ─── Session ──────────────────────────────────────────────────────────────────

def make_session(retries: int = 1) -> requests.Session:
    session = requests.Session()
    retry = Retry(total=retries, backoff_factor=0.3,
                  status_forcelist=[500, 502, 503, 504],
                  allowed_methods=["HEAD", "GET"])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

# ─── Core check ───────────────────────────────────────────────────────────────

def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    return raw

def is_valid_url(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False

def check_url(customer_name: str, url: str, timeout: float, session: requests.Session) -> Result:
    url = normalize_url(url)

    if not is_valid_url(url):
        return Result(customer_name=customer_name, url=url, status="unknown", note="URL không hợp lệ")

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    start = time.monotonic()
    try:
        # Thử HEAD trước — nhanh hơn
        resp = session.head(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
        )
        elapsed = int((time.monotonic() - start) * 1000)
        code = resp.status_code

        # Một số server không hỗ trợ HEAD → fallback GET với stream
        if code == 405:
            resp = session.get(url, headers=headers, timeout=timeout,
                               allow_redirects=True, stream=True)
            resp.close()
            code = resp.status_code
            elapsed = int((time.monotonic() - start) * 1000)

        status, note = STATUS_MAP.get(code, ("unknown", f"HTTP {code}"))
        return Result(customer_name=customer_name, url=url, status=status, http_code=code,
                      note=note, elapsed_ms=elapsed)

    except requests.exceptions.ConnectionError:
        return Result(customer_name=customer_name, url=url, status="unknown", note="Không kết nối được")
    except requests.exceptions.Timeout:
        elapsed = int((time.monotonic() - start) * 1000)
        return Result(customer_name=customer_name, url=url, status="unknown", note="Timeout", elapsed_ms=elapsed)
    except requests.exceptions.TooManyRedirects:
        return Result(customer_name=customer_name, url=url, status="unknown", note="Quá nhiều redirect")
    except Exception as e:
        return Result(customer_name=customer_name, url=url, status="unknown", note=str(e)[:60])

# ─── Display ──────────────────────────────────────────────────────────────────

STATUS_ICON = {
    "alive":   c(C.GREEN,  "✓ ALIVE  "),
    "dead":    c(C.RED,    "✗ DEAD   "),
    "unknown": c(C.YELLOW, "? UNKNOWN"),
}

def print_result(r: Result, idx: int, total: int):
    icon  = STATUS_ICON.get(r.status, STATUS_ICON["unknown"])
    code  = f"HTTP {r.http_code}" if r.http_code else "—"
    ms    = f"{r.elapsed_ms}ms" if r.elapsed_ms else ""
    idx_s = c(C.GRAY, f"[{idx:>3}/{total}]")
    name_s = f"[{r.customer_name[:15]}] " if r.customer_name else ""
    url_s = c(C.CYAN, name_s + r.url[:72] + ("…" if len(r.url) > 72 else ""))
    note  = c(C.GRAY, f"  {r.note}") if r.note else ""
    time_s = c(C.GRAY, f" {ms}") if ms else ""
    print(f"{idx_s} {icon}  {c(C.GRAY, code)}{time_s}  {url_s}{note}")

def print_summary(results: list[Result]):
    alive   = sum(1 for r in results if r.status == "alive")
    dead    = sum(1 for r in results if r.status == "dead")
    unknown = sum(1 for r in results if r.status == "unknown")
    total   = len(results)

    print()
    print(c(C.BOLD, "─" * 60))
    print(c(C.BOLD, "  KẾT QUẢ TỔNG HỢP"))
    print(c(C.BOLD, "─" * 60))
    print(f"  Tổng links    : {c(C.BOLD, str(total))}")
    print(f"  ✓ Còn sống    : {c(C.GREEN, str(alive))}")
    print(f"  ✗ Đã chết     : {c(C.RED, str(dead))}")
    print(f"  ? Không xác định: {c(C.YELLOW, str(unknown))}")
    print(c(C.BOLD, "─" * 60))
    if total:
        print(f"  Tỉ lệ sống    : {c(C.CYAN, f'{alive/total*100:.1f}%')}")
    print()

# ─── Export ───────────────────────────────────────────────────────────────────

def export_csv(results: list[Result], path: str):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Tên KH", "URL", "Trạng thái", "HTTP Code", "Ghi chú", "Thời gian (ms)", "Giờ check"])
        for r in results:
            writer.writerow([r.customer_name, r.url, r.status, r.http_code or "", r.note, r.elapsed_ms, r.checked_at])
    print(c(C.GREEN, f"  → Đã xuất: {path}"))

def export_txt(results: list[Result], kind: str, path: str):
    filtered = [r for r in results if r.status == kind]
    with open(path, "w", encoding="utf-8") as f:
        for r in filtered:
            f.write(r.url + "\n")
    print(c(C.GRAY, f"  → {kind.upper()} links: {path} ({len(filtered)} dòng)"))

# ─── Main ─────────────────────────────────────────────────────────────────────

def load_csv(path: str) -> list[tuple[str, str]]:
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
        
        name_idx = 0
        url_idx = 1 if len(header) > 1 else 0
        is_header = False
        
        for i, h in enumerate(header_lower):
            if h in ("tên kh", "tên khách hàng", "name"):
                name_idx = i
                is_header = True
            if h in ("facebook", "link fb", "url", "link"):
                url_idx = i
                is_header = True
            if h in ("ngày tìm", "sđt", "email"):
                is_header = True
                
        if not is_header:
            f.seek(0)
            reader = csv.reader(f)
            
        for row in reader:
            if not row:
                continue
                
            name = row[name_idx].strip() if name_idx < len(row) else ""
            url = row[url_idx].strip() if url_idx < len(row) else ""
            
            # Heuristic: Tìm cột chứa link nếu url_idx không có
            if "http" not in url and "fb.com" not in url and "facebook.com" not in url:
                for item in reversed(row):
                    item = item.strip()
                    if item.startswith("http") or "fb.com" in item or "facebook.com" in item:
                        url = item
                        break
                        
            if url and not url.startswith("#"):
                data.append((name, url))
                
    return data

def parse_args():
    parser = argparse.ArgumentParser(
        description="FB Link Checker — kiểm tra khả năng sống qua HTTP HEAD",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python checkVer1.py input.csv
  python checkVer1.py input.csv -o results.csv
  python checkVer1.py input.csv -w 10 -d 0.3 -t 8
  python checkVer1.py input.csv --alive alive.txt --dead dead.txt
        """
    )
    parser.add_argument("input",      help="File CSV chứa danh sách (Cột 1: Tên KH, Cột 2: Link FB)")
    parser.add_argument("-o", "--output",  default="", help="Xuất kết quả ra CSV")
    parser.add_argument("-w", "--workers", type=int, default=5, help="Số luồng song song (mặc định: 5)")
    parser.add_argument("-t", "--timeout", type=float, default=10, help="Timeout mỗi request (giây, mặc định: 10)")
    parser.add_argument("-d", "--delay",   type=float, default=0.5, help="Delay giữa các request (giây, mặc định: 0.5)")
    parser.add_argument("--alive", default="", help="Xuất các link còn sống ra file txt")
    parser.add_argument("--dead",  default="", help="Xuất các link đã chết ra file txt")
    return parser.parse_args()

def main():
    args = parse_args()
    data = load_csv(args.input)
    total = len(data)

    if not total:
        print(c(C.YELLOW, "[!] Không có URL nào để check."))
        sys.exit(0)

    print()
    print(c(C.BOLD, f"  FB Link Checker  —  {total} links"))
    print(c(C.GRAY,  f"  Workers: {args.workers}  |  Timeout: {args.timeout}s  |  Delay: {args.delay}s"))
    print(c(C.BOLD, "─" * 60))
    print()

    results: list[Result] = [None] * total
    session = make_session()

    # Sequential với delay để tránh bị rate-limit FB
    # (dùng workers=1 cho an toàn; tăng lên nếu muốn nhanh hơn)
    if args.workers == 1:
        for i, (name, url) in enumerate(data, 1):
            r = check_url(name, url, args.timeout, session)
            results[i - 1] = r
            print_result(r, i, total)
            if i < total and args.delay > 0:
                time.sleep(args.delay)
    else:
        # Multi-thread: chia delay đều
        done = 0
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(check_url, name, url, args.timeout, session): idx
                       for idx, (name, url) in enumerate(data)}
            for future in as_completed(futures):
                idx = futures[future]
                r = future.result()
                results[idx] = r
                done += 1
                print_result(r, done, total)
                time.sleep(args.delay / args.workers)

    print_summary(results)

    # Xuất file
    if args.output:
        export_csv(results, args.output)
    if args.alive:
        export_txt(results, "alive", args.alive)
    if args.dead:
        export_txt(results, "dead", args.dead)

    # Auto-export CSV nếu không chỉ định
    if not args.output and not args.alive and not args.dead:
        auto = f"fb_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        export_csv(results, auto)

if __name__ == "__main__":
    main()