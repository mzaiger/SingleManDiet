"""
update_walmart_search_urls.py

Walmart /ip/ product pages break constantly, so this turns PRODUCT_URL on
every item in candidate_pool.json into a Walmart SEARCH link built from the
product name -- the same query as the item's Instacart link (falls back to the shared name
cleaner when there is none):
    https://www.walmart.com/search?q=<product+name+with+pluses>

The original product page is saved first in PRODUCT_URL_OLD (never
overwritten once set), so nothing is lost. No network calls.

Usage:
    python update_walmart_search_urls.py              # convert in place
    python update_walmart_search_urls.py --dry-run    # show counts, write nothing
    python update_walmart_search_urls.py --revert     # put PRODUCT_URL_OLD back into PRODUCT_URL
    python update_walmart_search_urls.py --input other.json --output other.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import kroger_new_items as kni

DEFAULT_INPUT = "candidate_pool.json"


def save_pool(path, pool):
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(pool, f, indent=2, ensure_ascii=False)
        f.write("\n")
    Path(tmp).replace(path)


def instacart_query(item):
    """The k=... query already on the item's INSTACART_URL, so the Walmart
    search is literally the same search as the Instacart one."""
    m = re.search(r"[?&]k=([^&]+)", item.get("INSTACART_URL") or "")
    return m.group(1) if m else ""


def is_search_url(url):
    return "walmart.com/search" in (url or "")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=DEFAULT_INPUT)
    ap.add_argument("--output", default=None, help="default: same as input")
    ap.add_argument("--revert", action="store_true", help="restore PRODUCT_URL from PRODUCT_URL_OLD")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output) if args.output else in_path
    pool = json.load(open(in_path, encoding="utf-8"))

    changed = kept_old = no_name = 0
    for item in pool:
        if args.revert:
            old = item.get("PRODUCT_URL_OLD")
            if old and item.get("PRODUCT_URL") != old:
                item["PRODUCT_URL"] = old
                changed += 1
            continue

        cur = item.get("PRODUCT_URL") or ""
        q = instacart_query(item)
        new = ("https://www.walmart.com/search?q=" + q) if q else \
              kni.build_walmart_search_url(item.get("PRODUCT_NAME") or item.get("name") or "")
        if not new:
            no_name += 1
            continue
        if cur and not is_search_url(cur) and not item.get("PRODUCT_URL_OLD"):
            item["PRODUCT_URL_OLD"] = cur  # keep the original product page
            kept_old += 1
        if cur != new:
            item["PRODUCT_URL"] = new
            changed += 1

    print(f"{'Would change' if args.dry_run else 'Changed'} {changed} PRODUCT_URL(s); "
          f"saved {kept_old} old product-page URL(s) to PRODUCT_URL_OLD; {no_name} had no name.",
          file=sys.stderr)
    if args.dry_run:
        return
    save_pool(out_path, pool)
    print(f"Saved -> {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
