"""
Single Man's Diet -- fill in the VALUE MEAL pictures that are still EMPTY.

STEP 2 of the two-step manual process for value meals:
  1. "Pull value meals (manual)"               -> pull_value_meals.py          adds value meals with an empty picture
  2. "Fill missing value meal images (manual)" -> refresh_value_meal_images.py  finds pictures for the empty ones

Same search as refresh_images.py (DuckDuckGo Images, restaurant and item in double quotes, best-scoring
https result, looser fallback, throttling cool-downs, resumes by itself) -- it just works on
value_meals.json instead of meals.json. Only meals whose image_url is empty are touched.

Options: --restaurant "McDonald's"  --limit 25  --retry-failed  --redo  --delay 3
         --time-budget-minutes 100  --output path/to/value_meals.json
Dependencies: pip install requests ddgs
"""

import argparse
import random
import sys
import time
from datetime import datetime, timezone

import pull_meals as pm
import pull_value_meals as vm
import refresh_images as ri


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output", default=vm.OUTPUT_PATH, help="Path to value_meals.json")
    ap.add_argument("--restaurant", default="", help="Only this restaurant (exact name)")
    ap.add_argument("--limit", type=int, default=0, help="Stop after this many meals (0 = no limit)")
    ap.add_argument("--retry-failed", action="store_true", help="Also retry meals that used up their attempts")
    ap.add_argument("--redo", action="store_true", help="Clear existing pictures in scope and search them again")
    ap.add_argument("--delay", type=float, default=ri.DEFAULT_DELAY_SECONDS, help="Seconds between searches")
    ap.add_argument("--time-budget-minutes", type=float, default=ri.DEFAULT_TIME_BUDGET_MINUTES)
    args = ap.parse_args()

    if ri.DDGS is None:
        raise SystemExit("ddgs isn't installed (pip install ddgs).")

    restaurant = args.restaurant.strip()
    store = vm.load_store(args.output)
    if restaurant:
        match = [n for n in {m["restaurant"] for m in store["meals"]} if n.lower() == restaurant.lower()]
        if not match:
            raise SystemExit(f"No value meals saved for {restaurant!r}.")
        restaurant = match[0]

    scope = [m for m in store["meals"] if not restaurant or m["restaurant"] == restaurant]
    if args.redo:
        for m in scope:
            for k in ("image_url", "image_full_url", "_image_source", "_image_attempts", "_image_refresh_failures"):
                m.pop(k, None)
            m["image_url"] = ""
            m["image_full_url"] = ""
    if args.retry_failed:
        for m in scope:
            if not m.get("image_url"):
                m["_image_attempts"] = 0
                m.pop("_image_refresh_failures", None)

    def needs_image(m):
        return not m.get("image_url") and m.get("_image_attempts", 0) < ri.IMAGE_MAX_ATTEMPTS_PER_MEAL

    empty_total = sum(1 for m in scope if not m.get("image_url"))
    todo = [m for m in scope if needs_image(m)]
    if args.limit > 0:
        todo = todo[: args.limit]
    label = restaurant or "all restaurants"
    pm.log(f"Images: {empty_total} value meal(s) with an empty picture for {label}; {len(todo)} to search this run.")
    if not todo:
        pm.log("Nothing to do -- no empty pictures (or the rest used up their attempts; use --retry-failed).")
        return

    found = not_found = done = logged = strikes = 0
    stopped = False
    deadline = time.monotonic() + args.time_budget_minutes * 60
    try:
        for meal in todo:
            if time.monotonic() > deadline:
                pm.log(f"  time budget ({args.time_budget_minutes:g} min) reached -- run it again to continue.")
                break
            while True:
                try:
                    thumb, full, source = ri.find_image(meal["restaurant"], meal["name"])
                    strikes = 0
                    break
                except Exception as e:  # noqa: BLE001
                    strikes += 1
                    pm.log(f"  search failed ({strikes}/{ri.MAX_STRIKES}) for {meal['restaurant']} / {meal['name']}: {e}")
                    if strikes >= ri.MAX_STRIKES:
                        stopped = True
                        fails = meal["_image_refresh_failures"] = meal.get("_image_refresh_failures", 0) + 1
                        if fails >= ri.GIVE_UP_AFTER_STOPPED_RUNS:
                            meal["_image_attempts"] = ri.IMAGE_MAX_ATTEMPTS_PER_MEAL
                        break
                    cooldown = min(ri.COOLDOWN_BASE_SECONDS * 2 ** (strikes - 1), ri.COOLDOWN_MAX_SECONDS)
                    pm.log(f"  DuckDuckGo is throttling -- cooling down {cooldown}s, then retrying the same meal.")
                    time.sleep(cooldown)
            if stopped:
                pm.log("  too many failures in a row -- stopping and saving; run it again later to continue.")
                break

            meal["_image_attempts"] = meal.get("_image_attempts", 0) + 1
            meal.pop("_image_refresh_failures", None)
            if thumb:
                meal["image_url"] = thumb
                meal["image_full_url"] = full or ""
                meal["_image_source"] = source
                meal["_updated_at"] = datetime.now(timezone.utc).isoformat()
                found += 1
                if logged < ri.LOG_FIRST_URLS:
                    logged += 1
                    pm.log(f"  image {logged}/{ri.LOG_FIRST_URLS}: {meal['restaurant']} / {meal['name']} [{source}] -> {thumb}")
            else:
                not_found += 1
            done += 1
            if done % ri.SAVE_EVERY == 0:
                pm.log(f"  ...{done} searched ({found} pictures found, {not_found} not found)")
                vm.save_store(args.output, store)
            time.sleep(args.delay + random.uniform(0, ri.JITTER_SECONDS))
    finally:
        vm.save_store(args.output, store)

    left = sum(1 for m in scope if not m.get("image_url"))
    pm.log(f"Images finished: {done} value meal(s) searched -- {found} picture(s) added, {not_found} not found. "
           f"{left} still have an empty picture for {label}.")
    if left:
        pm.log("Run it again to continue where this left off.")


if __name__ == "__main__":
    sys.exit(main())
