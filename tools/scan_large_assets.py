"""Scan the repository for large static assets and print a sorted list.

Usage: python tools/scan_large_assets.py --min-mb 0.5
"""
import os
import argparse


def human_size(bytesize: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if bytesize < 1024:
            return f"{bytesize:.2f}{unit}"
        bytesize /= 1024
    return f"{bytesize:.2f}TB"


def scan(root: str, min_bytes: int):
    results = []
    for dirpath, dirnames, filenames in os.walk(root):
        # skip node_modules and .git
        if "node_modules" in dirpath.split(os.sep) or ".git" in dirpath.split(os.sep):
            continue
        for fn in filenames:
            try:
                p = os.path.join(dirpath, fn)
                s = os.path.getsize(p)
                if s >= min_bytes:
                    results.append((s, p))
            except Exception:
                continue
    results.sort(reverse=True)
    for s, p in results:
        print(f"{p} {human_size(s)}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--min-mb", type=float, default=0.5, help="Minimum file size in MB")
    args = p.parse_args()
    scan('.', int(args.min_mb * 1024 * 1024))


if __name__ == '__main__':
    main()
