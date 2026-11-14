# Single Man's Diet

A static website that builds a 7-day meal plan from **two pools at once**: the **frozen aisle** (~1,900 Walmart/Kroger products with Walmart and Instacart links) and **52 national fast food chains** (Gemini-estimated menu items with the restaurant's site and DoorDash / Uber Eats / Grubhub links). For every meal of the day you choose **no meal, frozen, or fast food**, and the plan lands each day within 250 calories of your target.

It is the merge of two earlier sites, *Poor Man's Frozen Meal Diet* and *Lazy Man's Fast Food Diet*. Everything from both repos is in here; the two data files are still separate (`candidate_pool.json` for frozen, `meals.json` for fast food).

> All calories, prices and servings are estimates or retailer data that can be stale. Menus and prices vary by location, so double-check at the store or restaurant.

## Repository layout

| Path | What it is |
|---|---|
| `index.html` | The planner: weight / age / activity → calorie target, the five meal sliders, filters, the two pool counters, the 7-day plan. |
| `products.html` | Combined product browser (frozen + fast food, filter by pool and meal type, fuzzy search) and the picker behind each meal's **select** button. |
| `shared.js` | Code both pages share: the two pools' normalizers, frozen breakfast / healthy / vegetarian rules, fast food flags, getters, delivery / retailer links, and the three slider icons. |
| `candidate_pool.json` | **Frozen pool.** Read by both pages and by every script in `DataCleaning/`. |
| `meals.json` | **Fast food pool.** Read by both pages and by `pull_meals.py`, `refresh_images.py`, `check_availability.py`. |
| `favicon.svg` | Tab icon (ice cube + burger). `favicon-frozen.svg` and `favicon-fast.svg` are the two single icons; the meal sliders use the same pictures. |
| `pull_meals.py`, `refresh_images.py`, `check_availability.py` | Fast food scripts (unchanged from the Fast Food repo; they stay at the repo root). |
| `DataCleaning/` | Frozen scripts, configs and source data (unchanged from the Frozen repo). Run from the repo root, e.g. `python DataCleaning/kroger_new_items.py`. |
| `.github/workflows/` | All seven workflows: the three fast food ones and the four frozen ones. |

## How the plan works (`index.html`)

- Enter weight, age and activity level to get a daily calorie target (or type your own). Each day lands within 250 calories of the target.
- **Meals per day (0 to 5):** a column of sliders for **Breakfast, Brunch, Lunch, Dinner, Late Dinner**. Slide each one to the top (red crossed circle = **no meal**), the middle (ice cube = **frozen**) or the bottom (burger = **fast food**). Out of the box: frozen breakfast, frozen lunch, fast food dinner, no brunch, no late dinner. Setting everything to "no" asks you to pick at least one.
- What each slot draws from:
  - **Breakfast**: breakfast items of the chosen pool.
  - **Brunch**: breakfast items *and* regular items of the chosen pool (fast food brunch never uses desserts).
  - **Lunch / Dinner**: regular items.
  - **Late Dinner**: fast food → **regular items and desserts** (shakes, slushes, malts, desserts); frozen → regular items.
- **Two pool counters** (Frozen / Fast): *meals matching your filters / meals your chosen slots can draw from*. Each narrows to what it can actually use: frozen only at breakfast → frozen breakfast items only; fast food only at lunch/dinner → regular items only; fast food only at late dinner → regular items + desserts; no fast food meals → the Fast circle reads 0 / 0 (same for Frozen).
- **Filters:** *Max per meal ($)*, *Healthy* and *Vegetarian*, applied to both pools with each pool's own rules (frozen: brand / keyword lists; fast food: Gemini's flags). If a filter would leave too few meals in a pool you use, that pool falls back to unfiltered and the page says so. Fast food desserts are only affected by the price cap and the vegetarian filter.
- **Each meal tile has its own pool slider** (ice cube ↔ burger). Move it, then press **regen** to pull a new meal from that pool (regen pulses yellow until you do). **Regen** otherwise swaps in a random meal from the same pool within 150 calories either way of the slot's original meal (`REGEN_CALORIE_RANGE` in `index.html`); the calorie anchor carries over when you switch pools.
- **Select** opens `products.html` on the pool the slider is set to, to hand-pick a meal; picking a meal from the other pool flips the slider to match.
- Links: frozen meals show **Walmart** and **Instacart**; fast food meals show the restaurant's own site (favicon) then **DoorDash, Uber Eats, Grubhub**.
- Weeks can be saved as tabs. They live in your browser only.
- The header uses both sites' photos, half and half (frozen on the left, fast food on the right), on both pages.

## Customizing the site

| What | Where |
|---|---|
| Default meal sliders | `DEFAULT_SEL` in `index.html` |
| Default max per meal | the `max-per-meal` input in `index.html` (and the reset in its change handler) |
| Slot rules (which sub-pool feeds which meal) | `subPoolKeys` in `index.html` |
| Frozen breakfast / healthy / vegetarian lists | top of `shared.js` |
| Fast food restaurants and their sites | `RESTAURANTS` in `pull_meals.py` (fallback copies in `shared.js`) |
| Header pictures | `--hero-frozen` / `--hero-fast` in the CSS of both HTML files (Unsplash License for the frozen one; "Digital Menu Boards in the Drive-Thru" by Erik Mclean on Pexels for the fast food one, with an inline illustration as fallback). |

---

# Frozen side (formerly *Poor Man's Frozen Meal Diet*)

Everything below about `candidate_pool.json` and `DataCleaning/`. The scripts read and write `../candidate_pool.json` (the repo root) via their config files, and the workflows call them as `python DataCleaning/<script>.py`.

### DataCleaning folder

Everything in `DataCleaning/`, roughly in the order you'd use it to build the
pool from scratch and then maintain it.

| File | What it does | Automated? |
|---|---|---|
| `frozen_food.csv` | The raw Walmart product export that `Dedup.py` reads (columns: `index, SHIPPING_LOCATION, DEPARTMENT, CATEGORY, SUBCATEGORY, BREADCRUMBS, SKU, PRODUCT_URL, PRODUCT_NAME, BRAND, PRICE_RETAIL, PRICE_CURRENT, PRODUCT_SIZE, PROMOTION, RunDate, tid`). In this copy of the repo it's an empty placeholder — drop a fresh export in before running `Dedup.py`. | — (data) |
| `Dedup.py` | Reads `frozen_food.csv`, drops a few unwanted categories (Frozen Desserts, Frozen Meat & Seafood, Frozen Produce, Frozen Potatoes), de-dupes by SKU, writes `frozen_food_deduped.csv`. | No — run manually when you refresh the source CSV. |
| `frozen_food_deduped.csv` | Output of `Dedup.py` (~1,800 unique items) and the input of `build_meal_pool.py`. | — (data) |
| `build_meal_pool.py` | Reads `frozen_food_deduped.csv`, cleans each product name, looks up calories and the serving size from the USDA FoodData Central API (serving = `householdServingFullText`, else `packageWeight`, cleaned), and writes `candidate_pool.json`. Resumable (skips SKUs already in the pool), rate-limited to 15 items/minute, `--debug` for a 3-minute trial run. Needs `USDA_API_KEY`. | No — run manually to (re)build the pool from scratch. |
| `rename_and_clean_serving.py` | One-time migration: renames the `servings_per_container` key to `serving` on every row and cleans messy values (e.g. `"2.71 OZ SERVING, 36 Servings Per Container"` → `"2.71 OZ SERVING"`). Idempotent; `--dry-run` to preview. **Note:** `index.html` and `kroger_new_items.py` use the `servings_per_container` key, so don't run this on the live pool unless they're changed to match. | No — one-time. |
| `AddImageUrl.py` | For every `active` item in `candidate_pool.json`, searches DuckDuckGo Images and writes the result to `image_url`. Rate-limit-conscious: one reused session, jittered delays, exponential backoff, a cooldown after repeated failures, per-query caching, and checkpointing so it's safe to Ctrl-C and re-run. `--limit`, `--force`, `--dry-run`, `--proxy`. No API key. | No — run manually. |
| `UpdateImageUrlsFromWalmartUrl.py` | Re-does `image_url` for **every** product that has a `PRODUCT_URL` (active or not; `--only-active` to limit): searches DuckDuckGo Images with the product's Walmart URL (query string removed) as the query and takes the **top result, whoever hosts it**. A product whose search finds nothing (or errors) keeps its existing `image_url` — it never blanks one. Same rate-limit hygiene as `AddImageUrl.py` (one session, jittered delays, backoff, cooldowns, checkpointing, `--proxy`); resumable via `_image_walmart_url_checked_at` (`--force` redoes all). `--limit`, `--dry-run`. About 3 hours for the full pool at default delays. No API key. | No — run manually. |
| `check_active_urls.py` | Uses Playwright (with stealth) to visit each item's `PRODUCT_URL` on walmart.com and tag it `active: true/false/null` (null = couldn't tell, e.g. bot-blocked), with reason/query/checked-URL metadata in `_active_check_*` fields. `--only-unknown`, `--limit`. | **Yes** — `check-active-urls.yml`, hourly. |
| `check_walmart_links.py` | Alternate liveness check: searches Google via Serper.dev for `site:walmart.com <product_id>` and checks whether walmart.com is the top result. Takes a URL list or a pool JSON (`--json`), resumable, `--debug` checks the first 10. Needs `SERPER_API_KEY`. | No — not wired into any workflow; `check_active_urls.py` is the one that runs. |
| `check_instacart_urls.py` | Searches `instacart <brand> <product name>` via Serper.dev and scans every result for one on instacart.com. Sets `INSTACART_URL` (only overwritten when a real match is found) and `instacart_active`. Resumable, `--limit`, `--debug`, `--out`. Needs `SERPER_API_KEY`. | No — run manually. |
| `update_instacart_urls.py` | Sets/refreshes `INSTACART_URL` on **every** row in `candidate_pool.json` from each row's own `PRODUCT_NAME` (text cut at the first comma, apostrophes kept as `%27`, everything else non-alphanumeric turned into `+`). Pure local transform — no network, no API key. `--only-missing` fills blanks only; `--dry-run` previews. (`kroger_new_items.py` builds its Instacart URLs with a slightly stricter cleanup that also drops sizes and numbers, so URLs on new Kroger rows can differ in form from ones this script writes.) | No — run manually. |
| `Max_Calories_Count.py` | Cross-checks each item's `calories` against USDA and Open Food Facts and keeps the **largest** of {current, USDA, Open Food Facts} — only ever raises a value, never lowers it. Adds `_calorie_max_checked_at` / `_calorie_max_source` to each item (that's what makes it resumable) and writes `calorie_max_check_diff.csv` listing every change, for spot-checking. `--limit`, `--recheck-all`, `--dry-run`. Needs `USDA_API_KEY`; Open Food Facts needs none. | No — run manually. |
| `gemini_meal_lookup.py` | Asks Gemini for an estimated calories-per-serving and price for a rotating batch of pool items (oldest/never-checked first), from Gemini's own knowledge — no live web search. Writes back only what differs, plus `_gemini_*` bookkeeping fields. Needs `GEMINI_KEY`. | **Yes** — `gemini-meal-lookup.yml`, weekly. |
| `gemini_meal_lookup.yaml` | Config for `gemini_meal_lookup.py` (not a workflow): which Gemini models to try in fallback order, batch shape (`items_per_call`, `calls_per_run`, `skip_inactive`), rate limiting, and the prompt template. | — (config) |
| `kroger_new_items.py` | Finds new frozen products in Kroger's catalog and adds up to 20 per run. Skips anything already in the pool (fuzzy name match, same brand); a new product gets its Kroger price, a Walmart URL/SKU (Serper.dev), calories (highest of USDA / Open Food Facts / Gemini), serving, image and Instacart link. Products it can't add are remembered in `kroger_skipped_upcs.json`. `--dry-run`, `--max-new-items`. Needs the Kroger, Serper, Gemini and USDA keys. | **Yes** — `kroger-new-items.yml`, 4× a day. |
| `kroger_new_items.yaml` | Config for `kroger_new_items.py` (also read by `kroger_add_skipped_items.py`): fuzzy-match threshold, Kroger search terms and store, per-run caps, and the pool / skipped-UPC file paths. | — (config) |
| `kroger_add_skipped_items.py` | Finishes the products in `kroger_skipped_upcs.json` that you gave a `walmart_url` by hand — same pipeline as `kroger_new_items.py` with your URL in place of the Serper Walmart lookup. Tags the UPC onto an existing row if that SKU is already in the pool. `--allow-missing-image`, `--dry-run`, `--limit`, `--max-minutes`. | No — manual run of `kroger-add-skipped-items.yml`. |
| `kroger_skipped_upcs.json` | Kroger UPCs `kroger_new_items.py` couldn't add (no matching Walmart page, no image, no calories), so they aren't retried. Add a `walmart_url` to an entry for `kroger_add_skipped_items.py` to pick up; it writes `status` / `detail` back onto the entries it handles. | — (data) |
| `skus_to_update.txt` | A plain list of Walmart SKUs, one per line. Not read by any script here. | — (data) |

### Workflows

| File | What it does |
|---|---|
| `.github/workflows/check-active-urls.yml` | Runs `check_active_urls.py --only-unknown --limit 100` hourly (`17 * * * *`) to keep dead Walmart links tagged `active: false`. Runnable manually with an overridable `batch_size`. |
| `.github/workflows/gemini-meal-lookup.yml` | Runs `gemini_meal_lookup.py` weekly (`0 0 * * 2`, Tuesdays 00:00 UTC) and commits the updated `candidate_pool.json`. Runnable manually with overridable `items_per_call` and `calls_per_run` (default 10 each). |
| `.github/workflows/kroger-new-items.yml` | Runs `kroger_new_items.py` 4× a day (`45 1,7,13,19 * * *`, UTC) and commits `candidate_pool.json` and `kroger_skipped_upcs.json`. Runnable manually with an overridable `max_new_items` (default 20). |
| `.github/workflows/kroger-add-skipped-items.yml` | Manual only (Actions tab → "Run workflow"): runs `kroger_add_skipped_items.py --allow-missing-image --max-minutes 100` — so products DuckDuckGo finds no image for are still added, with a blank `image_url` — and commits `candidate_pool.json` and `kroger_skipped_upcs.json`. Optional inputs: `limit` (max entries, 0 = all) and `dry_run`. Shares a concurrency group with `kroger-new-items.yml` so the two never edit the pool at the same time. |

#### Disabling a scheduled workflow

Two ways, without touching code:
1. **GitHub UI** — repo → Actions tab → select the workflow → "..." menu →
   "Disable workflow". Re-enable the same way. Nothing to commit.
2. **Edit the YAML** — remove or comment out the `schedule:` block (the
   `cron:` line). The `workflow_dispatch:` trigger, if left in place,
   still lets you run it manually from the Actions tab.

### Design notes

- **Gemini has no web search.** `gemini_meal_lookup.py` and
  `kroger_new_items.py` ask Gemini from its own training knowledge only.
  The `google_search` grounding tool was removed because its separate quota
  effectively needs a linked billing account. Consequences: Gemini
  *prices* are rough, possibly stale estimates (rows carry
  `_gemini_price_is_estimate: true`); calories hold up better since
  nutrition facts change less often; and Gemini is never asked for a source
  URL (with no search it would just be a plausible-looking fabrication). If
  billing is ever set up, adding `"tools": [{"google_search": {}}]` to the
  request body in `call_gemini_batch_single_model()` in
  `gemini_meal_lookup.py` restores live lookups (that tool can't be
  combined with the forced-JSON `responseMimeType` setting, so drop that
  too).
- **Gemini calorie guesses can be too low**, which is why calories use
  "largest wins" (`Max_Calories_Count.py`, and the same rule in
  `kroger_new_items.py`): a full entrée showing 5–10 calories essentially
  never happens, so taking the max of several sources rarely overshoots.
  It's a heuristic — spot-check `calorie_max_check_diff.csv`.
- **New Kroger rows are marked `active: true` right away.** Serper already
  confirmed a live walmart.com page, and `check_active_urls.py`'s
  Playwright checks are often bot-blocked, leaving items stuck at `null`.
  `check_active_urls.py` can still flip a row to `false` later.
- **Instacart links are guesses.** `INSTACART_URL` is a search-results URL
  built from the product name; only `check_instacart_urls.py` verifies
  anything, and only if you run it.

### Required secrets / environment variables

No API keys are hardcoded anywhere in this repo. Each script reads its key
from an environment variable at runtime:

| Variable | Used by | Required for |
|---|---|---|
| `USDA_API_KEY` | `build_meal_pool.py`, `Max_Calories_Count.py`, `kroger_new_items.py`, `kroger_add_skipped_items.py` | USDA FoodData Central calorie and serving lookups. |
| `SERPER_API_KEY` | `check_walmart_links.py`, `check_instacart_urls.py`, `kroger_new_items.py` | Serper.dev Google searches — Walmart/Instacart link checks, and finding each new product's Walmart URL/SKU. |
| `GEMINI_KEY` | `gemini_meal_lookup.py`, `kroger_new_items.py`, `kroger_add_skipped_items.py` | The weekly Gemini estimate workflow, and the Gemini calorie estimate for new products. |
| `KROGER_CLIENT_ID` / `KROGER_CLIENT_SECRET` | `kroger_new_items.py`, `kroger_add_skipped_items.py` | Kroger's OAuth client-credentials app (register at developer.kroger.com) — product catalog search and store lookup. |
| `KROGER_ZIP` | `kroger_new_items.py`, `kroger_add_skipped_items.py` | ZIP code, turned into the nearest Kroger-family store whose prices are used. Secret or repo variable. Not needed if a store id is set below. |
| `KROGER_LOCATION_ID` *(optional)* | `kroger_new_items.py`, `kroger_add_skipped_items.py` | Pins one specific store; wins over `KROGER_ZIP` and over `kroger.location_id` in `kroger_new_items.yaml`. |

Open Food Facts needs no key. `check_active_urls.py` and `AddImageUrl.py`
don't need any key either.

For GitHub Actions, the keys need to be repo secrets (Settings → Secrets
and variables → Actions), referenced in the relevant workflow's `env:`
block. `KROGER_ZIP` can be a secret or a repo variable (the workflow reads
either); `KROGER_LOCATION_ID` is read from a repo *variable*.

---

# Fast food side (formerly *Lazy Man's Fast Food Diet*)

Everything below about `meals.json` and the three scripts at the repo root.

### Setup

1. Put the files in a GitHub repo as shown above.
2. Get a Gemini API key (Google AI Studio) and add it as a repository secret named **`GEMINI_KEY`** (Settings, Secrets and variables, Actions).
3. Turn on GitHub Pages for the repo (Settings, Pages) so `index.html` is served.
4. Go to the **Actions** tab, open **Pull fast food meals (manual)** and click **Run workflow** once. This creates `meals.json`. Until it exists the site shows "Meal list not found yet."

The two Actions above are started by hand. The availability check (below) is the only one that runs on a schedule.

### How to update the data (two manual steps)

1. **Pull meals.** Actions tab, **Pull fast food meals (manual)**, Run workflow. New meals are added with an empty picture (`image_url` and `image_full_url` are `""`) and stamped with today's date. Each run only pulls the restaurants with the fewest items (up to 20 per run); run it again to keep going.
2. **Fill pictures.** Actions tab, **Fill missing meal images (manual)**, Run workflow. It searches DuckDuckGo only for meals whose picture is empty, so existing pictures are never touched. DuckDuckGo throttles, so a big batch can take several runs; each run picks up the meals that are still empty.

**Date updated.** Every meal has an `_updated_at` timestamp. Step 1 sets it on each new meal, and step 2 sets it again on each meal that gets a picture. `meals.json` also has a top-level `updated_at` that is refreshed every time either script saves. **Menu Items** (`products.html`) sorts by `_updated_at`, newest first, so the most recent pull or picture fill is at the top. Meals from before this field existed fall back to `_added_at`.

### Availability check (`check_availability.py`)

Runs **4 times a day** (03:23, 09:23, 15:23 and 21:23 UTC, so every Pacific-time day gets exactly 4 runs) and can also be started by hand. It marks every meal as sold in most states right now or not.

- **What is checked.** Gemini is asked, with today's date in the prompt, whether each meal is currently a regular item on that restaurant's U.S. menu in **most states / at most locations**. `"active": true` means yes. `"active": false` means discontinued, limited-time or seasonal and not on sale now, regional / test-market / only some locations, or the model isn't sure it exists. `index.html` leaves inactive meals out of plan generation (and out of its pool counter); meals not checked yet stay in. `products.html` still lists every meal, inactive ones included.
- **How much per run.** 40 meals per Gemini call, 20 calls per run = up to **800 meals per run**, spread round-robin over Flash 3.8, 3.7, 3.6 and 3.5 (about 5 calls each per run, so 4 runs use each model's 20 calls per Pacific day). A model that is out of quota or failing is skipped and the others take over. Settings: `AVAIL_ITEMS_PER_CALL`, `AVAIL_CALLS_PER_RUN`, `MAX_GEMINI_CALLS`.
- **Cycles.** Each meal remembers the cycle it was last checked in (`_avail_cycle`). When every meal has been checked, the cycle is closed (a summary goes into `availability.history`), the cycle number goes up and the whole pool is run through again. Meals added by the pull join the current cycle.
- **Tracking.** After each run the log, the Action's run summary and the commit message show the progress, for example `Cycle 2: 1600/8392 meals checked (19.1%) -- 1259 active, 341 inactive`. The same numbers are in `meals.json` under `availability` (`progress`, `last_run`, `history`, `quota`).
- **Quota.** It uses the same Gemini free tier as the pull, so the two compete if they use the same key. To give the check its own quota, add a second repository secret **`GEMINI_KEY_AVAIL`** from a different Google project; the workflow uses it when it exists and falls back to `GEMINI_KEY` otherwise.
- **Limit.** Gemini answers from its training, so a menu that changed recently can be wrong. Setting `AVAIL_USE_SEARCH=1` turns on Google Search grounding for fresher answers (off by default, it has its own quota).
- **Same lock.** The workflow shares the `pull-meals` concurrency group with the other two Actions, so they never edit `meals.json` at once.

Run locally: `GEMINI_KEY=your_key python check_availability.py` (needs `pull_meals.py` next to it).

### The restaurants

Meals can only come from these 52 chains. The official site is where each restaurant's favicon link on the page goes.

| Restaurant | Official site |
|---|---|
| Applebee's | [www.applebees.com](https://www.applebees.com/) |
| Arby's | [www.arbys.com](https://www.arbys.com/) |
| Blaze Pizza | [www.blazepizza.com](https://www.blazepizza.com/) |
| Buffalo Wild Wings | [www.buffalowildwings.com](https://www.buffalowildwings.com/) |
| Burger King | [www.bk.com](https://www.bk.com/) |
| Charleys Cheesesteaks | [www.charleys.com](https://www.charleys.com/) |
| Cheddar's | [www.cheddars.com](https://www.cheddars.com/) |
| Chick-fil-A | [www.chick-fil-a.com](https://www.chick-fil-a.com/) |
| Chili's | [www.chilis.com](https://www.chilis.com/) |
| Chipotle | [www.chipotle.com](https://www.chipotle.com/) |
| Cracker Barrel | [www.crackerbarrel.com](https://www.crackerbarrel.com/) |
| Culver's | [www.culvers.com](https://www.culvers.com/) |
| Dairy Queen | [www.dairyqueen.com](https://www.dairyqueen.com/) |
| Denny's | [www.dennys.com](https://www.dennys.com/) |
| Domino's | [www.dominos.com](https://www.dominos.com/) |
| Dunkin' | [www.dunkindonuts.com](https://www.dunkindonuts.com/) |
| Famous Dave's | [www.famousdaves.com](https://www.famousdaves.com/) |
| Firehouse Subs | [www.firehousesubs.com](https://www.firehousesubs.com/) |
| Five Guys | [www.fiveguys.com](https://www.fiveguys.com/) |
| Freddy's | [www.freddys.com](https://www.freddys.com/) |
| Godfather's Pizza | [www.godfathers.com](https://www.godfathers.com/) |
| IHOP | [www.ihop.com](https://www.ihop.com/) |
| Jersey Mike's Subs | [www.jerseymikes.com](https://www.jerseymikes.com/) |
| Jimmy John's | [www.jimmyjohns.com](https://www.jimmyjohns.com/) |
| Kentucky Fried Chicken | [www.kfc.com](https://www.kfc.com/) |
| Little Caesar's | [www.littlecaesars.com](https://www.littlecaesars.com/) |
| Long John Silver's | [www.ljsilvers.com](https://www.ljsilvers.com/) |
| McAlister's Deli | [www.mcalistersdeli.com](https://www.mcalistersdeli.com/) |
| McDonald's | [www.mcdonalds.com](https://www.mcdonalds.com/) |
| Moe's Southwest Grill | [www.moes.com](https://www.moes.com/) |
| Noodles & Company | [www.noodles.com](https://www.noodles.com/) |
| Olive Garden | [www.olivegarden.com](https://www.olivegarden.com/) |
| Outback Steakhouse | [www.outback.com](https://www.outback.com/) |
| Panda Express | [www.pandaexpress.com](https://www.pandaexpress.com/) |
| Panera | [www.panerabread.com](https://www.panerabread.com/) |
| Papa John's | [www.papajohns.com](https://www.papajohns.com/) |
| Papa Murphy's | [www.papamurphys.com](https://www.papamurphys.com/) |
| Pizza Hut | [www.pizzahut.com](https://www.pizzahut.com/) |
| Popeyes | [www.popeyes.com](https://www.popeyes.com/) |
| Qdoba | [www.qdoba.com](https://www.qdoba.com/) |
| Raising Cane's | [www.raisingcanes.com](https://www.raisingcanes.com/) |
| Red Robin | [www.redrobin.com](https://www.redrobin.com/) |
| Ruby Tuesday | [www.rubytuesday.com](https://www.rubytuesday.com/) |
| Slim Chickens | [www.slimchickens.com](https://www.slimchickens.com/) |
| Sonic Drive-In | [www.sonicdrivein.com](https://www.sonicdrivein.com/) |
| Starbucks | [www.starbucks.com](https://www.starbucks.com/) |
| Subway | [www.subway.com](https://www.subway.com/) |
| Taco Bell | [www.tacobell.com](https://www.tacobell.com/) |
| Taco John's | [www.tacojohns.com](https://www.tacojohns.com/) |
| Texas Roadhouse | [www.texasroadhouse.com](https://www.texasroadhouse.com/) |
| Wendy's | [www.wendys.com](https://www.wendys.com/) |
| Wingstop | [www.wingstop.com](https://www.wingstop.com/) |

The list lives in `RESTAURANTS` at the top of `pull_meals.py` and is copied into `meals.json`, which is what the page's "Where the meals come from" section shows. The pages also ignore any meal whose restaurant isn't on that list.

### How the data is pulled (`pull_meals.py`)

**Gemini, one restaurant per call.** Each call asks for up to 60 new items for one restaurant. The names already on file are sent along so Gemini only returns new ones; the list grows a little every run. Each item comes back with:

- `category`: `breakfast`, `regular` or `dessert` (desserts, slushes, shakes, malts, sweet blended drinks)
- `calories`, `price`, `serving`
- `vegetarian` and `healthy` (yes/no, set by Gemini; desserts and pizza are never healthy, and tacos aren't either unless they're street-style or Fresco, or from Chipotle or Qdoba)

Beverages, dips, sauces and condiments are excluded, and any item with an unknown category or an out-of-range calorie/price value is dropped.

**Serving rules (tacos and pizza slices).** Gemini reports a single taco or a single slice, and `pull_meals.py` converts it when saving (`apply_serving_rules`):

- A single taco (serving `1 taco`) is saved as **3 tacos**, with calories and price x3.
- A single pizza slice (serving `1 slice ...` on an item that is a pizza) is saved as **2 slices**, with calories x2. The price is doubled only for **Pizza Hut** slices under $7 (`SLICE_PRICE_DOUBLED_FOR`, `SLICE_PRICE_DOUBLE_BELOW`); other chains list a whole-pizza price on a one-slice item, so their prices are left as reported. Fractions are scaled too, e.g. `1 slice (1/8 pizza)` becomes `2 slices (2/8 pizza)`.
- Left alone: dessert pizzas (Dairy Queen Treatzza), Gordita Crunches, anything that is already several servings (`3 tacos`, `order of 3 tacos`, `2 rolled tacos`, `2 slices`, `1/4 pizza (2 slices)`), personal / individual / kids' / whole pizzas (`1 personal pizza`, `1 pizza (4 slices)`), combos (`1 slice pizza + 2 stix`), and "slices" of things that are not pizza (cheesecake, pie, loaves, ham).
- A leading "Single " is dropped from the name (`Single Chicken Taco` becomes `Chicken Taco`).
- Converted meals get `_serving_multiplier` (3 or 2). The rule skips meals that have it, and it also runs over `meals.json` every time the script starts, so saved meals can never be multiplied twice.

**Models and daily limits.** Gemini Flash **3.8, 3.7, 3.6, 3.5** are tried in that order. Each model has its own allowance of 20 calls per Pacific-time day (`MAX_GEMINI_CALLS`), and each run makes at most 20 calls (`MAX_CALLS_PER_RUN`), so a run does not go through every restaurant. At the start of each run the restaurants are sorted by how many meals `meals.json` already holds for each, **fewest items first** (never-pulled restaurants, for example ones just added to `RESTAURANTS`, go to the front), and the run works down that list until it hits its call limit. Only answers Google actually served count toward the allowance.

- A model that answers with a 4xx (out of quota, unknown model ID) is skipped for the rest of that day.
- A model that returns 503/errors makes that restaurant fall through to the next model. After 3 failures in a row the model is skipped for the rest of the run and tried again on the next run.

**Order of restaurants.** Nothing is remembered between runs except the meals themselves. Every run sorts all restaurants by item count again, fewest first, so whichever restaurants are thinnest at that moment go first. A restaurant that fails (for example Gemini is overloaded) is retried once in the same run, otherwise it stays near the front of the next sort.

**Pictures are not pulled here.** `pull_meals.py` does no image search at all. Every new meal is saved with `"image_url": ""` and `"image_full_url": ""`, and the Menu Items page shows "no image" until step 2 fills it in.

**Filling pictures (`refresh_images.py`).** To find pictures, open the **Actions** tab, choose **Fill missing meal images (manual)** and click **Run workflow** (or run `python refresh_images.py` locally). It only looks at meals whose `image_url` is empty. For each one it searches DuckDuckGo Images with the restaurant and the item **each in double quotes**, exactly as you would type it in the search box, and stores the first https image URL (`image_url`, plus the full-size `image_full_url` as a fallback). Olive Garden's Fettuccine Alfredo is searched as:

```
"Olive Garden" "Fettuccine Alfredo"
```

If that finds nothing, it tries again without any `(...)` in the item name (`"Chipotle" "Chicken Taco"` for `Chicken Taco (Soft Flour)`), then one looser search that keeps only the restaurant in quotes (turn that off with `IMAGE_FALLBACK_TO_WEB = False`). Each picture records which search found it in `_image_source`: `quoted` or `web` (the looser fallback). A meal that gets a picture also gets a new `_updated_at`. A meal where nothing was found stays empty and is tried again on later runs, up to 3 times (`_image_attempts`, `IMAGE_MAX_ATTEMPTS_PER_MEAL`); the **retry_failed** input gives those another go.

DuckDuckGo throttles fast searching, so the script pauses a few seconds between searches and, when a search fails, cools down (30 s up to 5 min) and retries the same meal; only after 6 failures in a row does it stop and save. There is no cap on the number of searches, only the time budget (default 110 minutes in the Action). Nothing is lost when a run stops early: just run it again and it continues with the meals that are still empty. Inputs: *retry_failed*, *restaurant* (just one chain, good for a quick test), *delay* (seconds between searches), *time budget*.

#### Running it locally

```bash
pip install requests ddgs
GEMINI_KEY=your_key python pull_meals.py      # step 1: pull meals (empty pictures)
python refresh_images.py                      # step 2: fill the empty pictures
```

`pull_meals.py` option: `--output path/to/meals.json`. (`requests` is all it needs; `ddgs` is only for step 2.)

`refresh_images.py` options: `--restaurant "Olive Garden"`, `--limit 25`, `--retry-failed`, `--delay 3`, `--time-budget-minutes 100`, `--output path/to/meals.json`.

Environment variables: `GEMINI_KEY` (required for step 1), `MAX_GEMINI_CALLS` (per model per day, default 20), `MAX_CALLS_PER_RUN` (default 20).

#### `meals.json` shape

```json
{
  "updated_at": "...",
  "allowed_restaurants": ["Applebee's", "..."],
  "restaurants": { "Chick-fil-A": { "site": "www.chick-fil-a.com", "last_pulled": "..." } },
  "quota": { "date": "2026-10-16", "calls": { "gemini-3.8-flash": 7 }, "exhausted": [] },
  "availability": { "cycle": 2, "progress": { "checked": 1600, "pool": 8392, "active": 1259, "inactive": 341 }, "history": [], "quota": {} },
  "meals": [
    {
      "restaurant": "McDonald's", "name": "Big Mac", "category": "regular",
      "calories": 590, "price": 6.49, "serving": "1 sandwich",
      "vegetarian": false, "healthy": false,
      "image_url": "https://...", "image_full_url": "https://...",
      "_updated_at": "2026-10-18T14:48:08+00:00",
      "active": true, "_avail_cycle": 2
    }
  ]
}
```

Fields that start with an underscore (`_added_at`, `_updated_at`, `_model`, `_image_attempts`, `_image_source`, `_serving_multiplier`, `_avail_cycle`, `_avail_checked_at`, `_avail_model`; older files may also have `_image_refreshed`, which is no longer used) are bookkeeping. If you ever want a clean start, delete `meals.json` and run the workflow again.

### Value meals (`pull_value_meals.py`, `value_meals.json`)

A separate pool for **value meals / combos**: a main + side + drink sold under one menu name ("Big Mac Meal", "#1 Combo"). Calories are the whole meal **with a diet drink**, i.e. the drink counts as 0, so it is the main and sides only; the price is the combo price; each meal also stores `serving` (what is in it) and `drink` (the diet drink assumed). One person's meal only: kids' meals, family bundles and a-la-carte items are not included.

Same two manual steps as the regular fast food data (Actions tab > Run workflow):

1. **Pull value meals (manual)** runs `pull_value_meals.py`: one Gemini call per restaurant, fewest meals first, pictures left empty. Optional inputs: a single restaurant, and "recheck" for chains earlier runs found nothing for.
2. **Fill missing value meal images (manual)** runs `refresh_value_meal_images.py`: the same DuckDuckGo quoted search as `refresh_images.py`, but on `value_meals.json`.

Only chains in `VALUE_MEAL_RESTAURANTS` (top of `pull_value_meals.py`) are pulled: Arby's, Burger King, Charleys Cheesesteaks, Chick-fil-A, Culver's, Dairy Queen, Firehouse Subs, Freddy's, Jersey Mike's, Jimmy John's, KFC, Long John Silver's, McAlister's, McDonald's, Popeyes, Raising Cane's, Slim Chickens, Sonic, Subway, Taco Bell, Taco John's, Wendy's, Wingstop, plus borderline Panera (You Pick Two), Qdoba, Moe's and Panda Express. A chain Gemini finds nothing for is marked `has_value_meals: false` and skipped later. To try another chain from the approved list, use the restaurant input (e.g. `--restaurant "Little Caesar's"`). Gemini's daily allowance is per API key but each JSON counts its own calls, so running both pulls on one day can hit Google's limit early; a model that says "quota" is skipped for the run.

The planner pages (`index.html`, `products.html`) do not read `value_meals.json` yet.

### Notes and limits

- Gemini's menu knowledge can be wrong or out of date. Numbers are estimates, not live menu data.
- Pictures come from DuckDuckGo searches for the quoted restaurant and item (step 2), but they aren't verified, so a picture may not match the item exactly (menus change and some items have no good photo online).
- Delivery-app search links go to each app's search page; results depend on your location.
- DuckDuckGo rate-limits aggressively, so a big backlog of pictures fills in over several runs of the image Action. Until then those meals show "no image".

