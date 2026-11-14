"""
Single Man's Diet -- VALUE MEAL puller (run by hand: GitHub Actions > "Pull value meals (manual)").

STEP 1 of a two-step manual process, the same shape as pull_meals.py / refresh_images.py:
  1. "Pull value meals (manual)"          -> pull_value_meals.py          adds value meals with an EMPTY picture
  2. "Fill missing value meal images (manual)" -> refresh_value_meal_images.py  finds pictures for the empty ones

What it pulls: the restaurant's VALUE MEALS / COMBOS -- an entree + side + drink sold together under
one menu name or number ("Big Mac Meal", "#1 Combo", "Original Chicken Sandwich Combo"). The calories
stored are the whole meal WITH A DIET DRINK: the drink is counted as zero-calorie (Diet Coke, Diet Pepsi,
Coke Zero, unsweetened tea, water), so "calories" = entree + side(s) only. "price" is the combo price.
Kids' meals, family/group bundles and a-la-carte items are not included (pull_meals.py has those).

Which restaurants: ONLY the ones in VALUE_MEAL_RESTAURANTS below -- the chains from the approved list
(pull_meals.py RESTAURANTS) that sell combos. Chains without them (Chipotle, Five Guys, the sit-down
restaurants, most pizza chains...) are left out. If a chain on the list turns out to have no value meals,
Gemini returns nothing for it, it is marked has_value_meals=false, and later runs skip it (--recheck
tries it again). To test any chain from the full approved list: --restaurant "Little Caesar's".

Everything else works like pull_meals.py: one Gemini call per restaurant, fewest items first, models
Flash 3.8 / 3.7 / 3.6 / 3.5 in order with their daily allowance, progress saved after every call, and
already-known names sent back so each pull returns NEW meals only. Data goes to value_meals.json.
Anything already in meals.json is skipped too (its combo-like names, e.g. Raising Cane's "The Box
Combo", are sent to Gemini as ALREADY KNOWN and exact name repeats are dropped on save), so the two
files never hold the same meal twice.
NOTE: the Gemini daily allowance is per API key, but each JSON counts its own calls, so running this
and the regular pull on the same day can hit Google's real limit sooner than the counters say; a
model that answers "quota" is simply skipped for the rest of the run.

Env var required: GEMINI_KEY  (missing -> the run is skipped, exit 0)
Run locally:  GEMINI_KEY=xxxx python pull_value_meals.py [--restaurant "McDonald's"] [--recheck]
Dependencies: pip install requests
"""

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone

import pull_meals as pm

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(_SCRIPT_DIR, "value_meals.json")
MEALS_PATH = pm.OUTPUT_PATH            # meals.json: anything already saved there is never pulled again

MAX_NEW_MEALS_PER_CALL = 40
MIN_CALORIES, MAX_CALORIES = 150, 3500   # whole meal, diet drink counted as 0
MIN_PRICE, MAX_PRICE = 2.00, 30.00       # one person's combo

# The approved restaurants that sell value meals / combos. Edit this list to add or drop a chain.
# The last four are borderline (a "meal deal" / "plate" / "You Pick Two" rather than a classic numbered
# combo); Gemini decides, and a chain it finds nothing for is marked has_value_meals=false.
VALUE_MEAL_RESTAURANTS = [
    "Arby's", "Burger King", "Charleys Cheesesteaks", "Chick-fil-A", "Culver's", "Dairy Queen",
    "Firehouse Subs", "Freddy's", "Jersey Mike's Subs", "Jimmy John's", "Kentucky Fried Chicken",
    "Long John Silver's", "McAlister's Deli", "McDonald's", "Popeyes", "Raising Cane's",
    "Slim Chickens", "Sonic Drive-In", "Subway", "Taco Bell", "Taco John's", "Wendy's", "Wingstop",
    # borderline:
    "Panera", "Qdoba", "Moe's Southwest Grill", "Panda Express",
]

CATEGORIES = ("breakfast", "regular")

PROMPT = """You are building a menu database for a calorie-counting meal planner.

Restaurant: {restaurant}
This restaurant is a U.S. national chain.

List the VALUE MEALS / COMBO MEALS sold on the standard U.S. menu of {restaurant} -- and ONLY {restaurant}. A value meal is a main item bundled with a side and a drink and sold as one menu choice, e.g. "Big Mac Meal", "#2 Combo", "Crunchwrap Supreme Combo", "Chicken Sandwich Meal", "You Pick Two with a drink". Never include items from any other restaurant and never invent items. If {restaurant} does not sell value meals / combos that include a drink, return an EMPTY array.

DO NOT include:
- Single a-la-carte items (a sandwich, fries or a drink alone).
- Kids' meals, family meals, party packs, boxes meant for several people, catering and limited-time bundles for groups. One person's meal only.
- Anything that has no drink in the bundle.

Sort every meal into one of two categories: "breakfast" (sold on the breakfast menu) or "regular" (everything else).

For each meal give:
- "name": the menu name, e.g. "Big Mac Meal" or "#1 Original Combo" (do not include the restaurant name)
- "category": "breakfast" or "regular"
- "calories": total calories of the WHOLE meal with a DIET drink. Count the main item and the side(s) at the default size the combo comes with, and count the drink as 0 calories (assume Diet Coke / Diet Pepsi / Coke Zero or unsweetened iced tea, as the chain sells). An integer.
- "price": typical U.S. menu price in dollars of the combo -- a number such as 9.49. An estimate; prices vary by location.
- "serving": what is in the meal, e.g. "Big Mac, medium fries" (food only, no drink)
- "drink": the diet / zero-calorie drink assumed, with size, e.g. "medium Diet Coke"
- "vegetarian": true only if the meal as normally served has no meat, poultry or fish
- "healthy": true only if a reasonable dietitian would call it one of the healthier choices on this menu (grilled or lean protein, not deep-fried, not heavy on cheese or sugar). Most combos are false.

Return at most {max_items} meals, best-known and most-ordered first. Do NOT include any meal whose name appears in the ALREADY KNOWN list below (treat small spelling differences as the same). If you cannot find any more genuinely new value meals, return fewer -- or an empty array.

ALREADY KNOWN for {restaurant} ({known_count} meals):
{known_block}

Return ONLY a JSON array of objects with exactly the keys above."""

RESPONSE_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING"},
            "category": {"type": "STRING", "enum": list(CATEGORIES)},
            "calories": {"type": "INTEGER"},
            "price": {"type": "NUMBER"},
            "serving": {"type": "STRING"},
            "drink": {"type": "STRING"},
            "vegetarian": {"type": "BOOLEAN"},
            "healthy": {"type": "BOOLEAN"},
        },
        "required": ["name", "category", "calories", "price", "serving", "drink", "vegetarian", "healthy"],
    },
}

log = pm.log


# ---------------------------------------------------------------------------
# JSON store
# ---------------------------------------------------------------------------

def load_store(path):
    store = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                store = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise SystemExit(f"Could not read {path}: {e} -- fix or delete it and re-run.")
    if not isinstance(store, dict):
        raise SystemExit(f"{path} should hold a JSON object; refusing to overwrite it.")
    store.setdefault("meals", [])
    store.setdefault("restaurants", {})
    store.setdefault("quota", {"date": "", "calls": {}, "exhausted": []})
    sites = pm.RESTAURANT_SITES
    for name in VALUE_MEAL_RESTAURANTS:
        entry = store["restaurants"].setdefault(name, {})
        entry["site"] = sites.get(name, "")
        entry.setdefault("last_pulled", "")
        entry.setdefault("has_value_meals", None)     # None = not checked yet
    store["allowed_restaurants"] = list(VALUE_MEAL_RESTAURANTS)
    return store


def save_store(path, store):
    store["updated_at"] = datetime.now(timezone.utc).isoformat()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


# Names in meals.json that read like a value meal / combo (kids' meals, "Club" sandwiches and
# sub names like "Cold Cut Combo" don't count). These are shown to Gemini as ALREADY KNOWN.
_COMBO_NAME_RE = re.compile(r"\b(combo|meal|box|plate|bundle)\b", re.I)
_NOT_COMBO_RE = re.compile(r"kid|jr\.|cold cut combo|\bclub\b|value (fries|onion|order)", re.I)


def load_existing_meals(path):
    """Reads meals.json (if there) and returns {restaurant: [names]} -- every name, so exact repeats
    are skipped when saving."""
    out = {}
    try:
        with open(path, encoding="utf-8") as f:
            for m in json.load(f).get("meals", []):
                out.setdefault(m.get("restaurant", ""), []).append(m.get("name", ""))
    except (OSError, json.JSONDecodeError, AttributeError):
        log(f"Could not read {path}; not checking value meals against it.")
    return out


def combo_like(names):
    return [n for n in names if _COMBO_NAME_RE.search(n) and not _NOT_COMBO_RE.search(n)]


def meal_key(restaurant, name):
    return f"{restaurant.lower()}|{pm.normalize_name(name)}"


def clean_meal(raw, restaurant):
    """Validates one Gemini value meal. Returns a meal dict or None."""
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name", "")).strip()
    if not name or len(name) > 120:
        return None
    name = re.sub(rf"^{re.escape(restaurant)}[\s'’]*s?\s+", "", name, flags=re.I).strip() or name
    category = str(raw.get("category", "")).strip().lower()
    if category not in CATEGORIES:
        return None
    try:
        calories = int(round(float(raw.get("calories"))))
        price = round(float(str(raw.get("price")).replace("$", "").strip()), 2)
    except (TypeError, ValueError):
        return None
    if not (MIN_CALORIES <= calories <= MAX_CALORIES and MIN_PRICE <= price <= MAX_PRICE):
        return None
    drink = str(raw.get("drink", "")).strip()[:60]
    if not drink:
        return None                                   # a value meal has a drink
    if re.search(r"\bkids?\b|family|party|catering|\bfeast\b|for\s+(?:2|two|3|three|4|four)\b", name, re.I):
        return None                                   # one person's meal only
    return {
        "restaurant": restaurant,
        "name": name,
        "category": category,
        "meal_type": "value_meal",
        "calories": calories,                          # whole meal, diet drink counted as 0
        "price": price,
        "serving": str(raw.get("serving", "")).strip()[:120] or "1 meal",
        "drink": drink,
        "vegetarian": bool(raw.get("vegetarian")),
        "healthy": bool(raw.get("healthy")),
        "image_url": "",                               # left empty; refresh_value_meal_images.py fills it in
        "image_full_url": "",
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def sort_fewest_first(store, names):
    counts = {}
    for m in store["meals"]:
        counts[m["restaurant"]] = counts.get(m["restaurant"], 0) + 1
    return sorted(names, key=lambda n: counts.get(n, 0))


def pull_one(store, restaurant, key, limiter, known, existing=None):
    known_names = [m["name"] for m in store["meals"] if m["restaurant"] == restaurant]
    in_meals_json = combo_like((existing or {}).get(restaurant, []))   # already in meals.json
    known_names = known_names + [n for n in in_meals_json if meal_key(restaurant, n) not in
                                 {meal_key(restaurant, k) for k in known_names}]
    shown = known_names[-pm.KNOWN_NAMES_SENT_PER_CALL:]
    prompt = PROMPT.format(
        restaurant=restaurant, max_items=MAX_NEW_MEALS_PER_CALL, known_count=len(known_names),
        known_block="\n".join(f"- {n}" for n in shown) if shown else "(none yet)")
    raw_items, model_used = pm.ask_gemini(prompt, key, limiter, store["quota"], RESPONSE_SCHEMA)

    now = datetime.now(timezone.utc).isoformat()
    added = rejected = dupes = 0
    for raw in raw_items:
        meal = clean_meal(raw, restaurant)
        if meal is None:
            rejected += 1
            continue
        k = meal_key(restaurant, meal["name"])
        if k in known:
            dupes += 1
            continue
        known.add(k)
        meal["_added_at"] = now
        meal["_updated_at"] = now
        meal["_model"] = model_used
        store["meals"].append(meal)
        added += 1

    entry = store["restaurants"][restaurant]
    entry["last_pulled"] = now
    if added or known_names or in_meals_json:
        entry["has_value_meals"] = True
    elif not raw_items:
        entry["has_value_meals"] = False               # nothing known, nothing returned: no value meals here
    log(f"  {restaurant}: +{added} new, {dupes} already known, {rejected} rejected "
        f"({len(raw_items)} returned by {model_used})"
        + ("  -> no value meals, will be skipped next time" if entry["has_value_meals"] is False else "") + ".")
    return added


def pull_meals(store, key, out_path, names, meals_path=None):
    today = pm.pacific_today()
    quota = store["quota"]
    if quota.get("date") != today:
        quota.clear()
        quota.update({"date": today, "calls": {}, "exhausted": []})
    quota.setdefault("calls", {})
    quota.setdefault("exhausted", [])
    budget = sum(pm.MAX_GEMINI_CALLS_PER_DAY - quota["calls"].get(m, 0) for m in pm.models_available(quota))
    if budget <= 0:
        log(f"Every model is at its daily limit on {today} Pacific -- nothing pulled this run.")
        return

    queue = sort_fewest_first(store, names)
    log(f"Gemini: up to {budget} call(s) left today. Run order starts with: "
        f"{', '.join(queue[:pm.MAX_GEMINI_CALLS_PER_RUN])}.")
    known = {meal_key(m["restaurant"], m["name"]) for m in store["meals"]}
    existing = load_existing_meals(meals_path) if meals_path else {}
    # Exact names already in meals.json count as known, so they are never added a second time.
    known |= {meal_key(r, n) for r, ns in existing.items() for n in ns}
    log(f"Skipping {sum(len(v) for v in existing.values())} name(s) already in {os.path.basename(meals_path or '')}.")
    limiter = pm._RateLimiter(pm.MIN_CALL_INTERVAL_SECONDS)
    failed, retried, pulled = [], False, []
    successes = attempts = added_total = 0
    max_attempts = budget * 2

    while pm.models_available(quota) and successes < pm.MAX_GEMINI_CALLS_PER_RUN and attempts < max_attempts:
        if not queue:
            if failed and not retried:
                retried = True
                log(f"  {len(failed)} restaurant(s) failed -- waiting {pm.RETRY_PASS_DELAY_SECONDS}s for one more try.")
                time.sleep(pm.RETRY_PASS_DELAY_SECONDS)
                queue, failed = failed, []
                continue
            break                                       # one pass over the list per run
        restaurant = queue.pop(0)
        attempts += 1
        try:
            added = pull_one(store, restaurant, key, limiter, known, existing)
        except pm.QuotaExceeded as e:
            log(f"  {restaurant}: {e} -- stopping; the next run continues.")
            save_store(out_path, store)
            return
        except Exception as e:  # noqa: BLE001
            log(f"  {restaurant}: failed ({e}); retried once, then left for the next run.")
            failed.append(restaurant)
            save_store(out_path, store)
            continue
        successes += 1
        added_total += added
        pulled.append(restaurant)
        save_store(out_path, store)

    log(f"Gemini: {successes} restaurant(s) pulled ({', '.join(pulled) or 'none'}), {added_total} new value meal(s); "
        f"calls used today (Pacific) per model: {quota['calls']}.")
    save_store(out_path, store)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output", default=OUTPUT_PATH, help="Path to value_meals.json")
    ap.add_argument("--restaurant", default="", help="Only this restaurant (any chain on the approved list, exact name)")
    ap.add_argument("--meals", default=MEALS_PATH, help="Path to meals.json (names already there are skipped)")
    ap.add_argument("--recheck", action="store_true", help="Also retry restaurants marked has_value_meals=false")
    args = ap.parse_args()

    store = load_store(args.output)
    names = list(VALUE_MEAL_RESTAURANTS)
    wanted = args.restaurant.strip()
    if wanted:
        match = [n for n in pm.RESTAURANT_NAMES if n.lower() == wanted.lower()]
        if not match:
            raise SystemExit(f"Unknown restaurant {wanted!r}. Choose one of: {', '.join(pm.RESTAURANT_NAMES)}")
        names = match
        entry = store["restaurants"].setdefault(match[0], {"site": pm.RESTAURANT_SITES[match[0]], "last_pulled": "",
                                                           "has_value_meals": None})
        if match[0] not in store["allowed_restaurants"]:
            store["allowed_restaurants"].append(match[0])
    elif not args.recheck:
        names = [n for n in names if store["restaurants"][n].get("has_value_meals") is not False]
    if args.recheck:
        for n in names:
            store["restaurants"][n]["has_value_meals"] = None

    key = os.environ.get("GEMINI_KEY")
    if not key:
        log("No GEMINI_KEY set -- skipping the Gemini value meal pull.")
    else:
        pull_meals(store, key, args.output, names, args.meals)

    save_store(args.output, store)
    no_image = sum(1 for m in store["meals"] if not m.get("image_url"))
    none = [n for n, e in store["restaurants"].items() if e.get("has_value_meals") is False]
    log(f"Done. value_meals.json has {len(store['meals'])} value meals; {no_image} still need a picture "
        f"(run refresh_value_meal_images.py)." + (f" No value meals at: {', '.join(none)}." if none else ""))


if __name__ == "__main__":
    main()
