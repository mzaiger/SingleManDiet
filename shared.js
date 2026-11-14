/* Single Man's Diet -- code shared by index.html and products.html.
 *
 * Two pools feed the whole site and stay in two separate JSON files:
 *   candidate_pool.json  frozen-aisle products (Walmart / Kroger data)   -> source "frozen"
 *   meals.json           fast food menu items (Gemini estimates)         -> source "fast"
 * Both are turned into one common item shape here (normalizeFrozenItem /
 * normalizeFastItem) so the planner and the product list treat them alike.
 * Every item carries:  source ("frozen" | "fast")  and  _cat ("breakfast" |
 * "regular" | "dessert" -- frozen items are only ever breakfast or regular).
 */

/* ---------- Icons ---------------------------------------------------------
 * Three pictures used by the meal sliders and the product list:
 *   ic-frozen  the ice cube   (the Frozen site's tab icon)
 *   ic-fast    the burger     (the Fast Food site's tab icon, favicon-fast.svg)
 *   ic-no      red circle with a strike through it ("no meal here")
 * Injected once per page; use them with <svg class="ic"><use href="#ic-frozen"/></svg>. */
const SM_SPRITE = '<svg xmlns="http://www.w3.org/2000/svg" style="position:absolute;width:0;height:0;overflow:hidden" aria-hidden="true" focusable="false">'
  + '<symbol id="ic-no" viewBox="0 0 64 64"><circle cx="32" cy="32" r="25" fill="none" stroke="#D93025" stroke-width="8"/><line x1="14.3" y1="14.3" x2="49.7" y2="49.7" stroke="#D93025" stroke-width="8" stroke-linecap="round"/></symbol>'
  + '<symbol id="ic-frozen" viewBox="0 0 64 64">'
  +   '<polygon points="32,5 55,18 32,31 9,18" fill="#DDF3FF"/>'
  +   '<polygon points="9,18 32,31 32,59 9,45" fill="#6CC3F5"/>'
  +   '<polygon points="55,18 32,31 32,59 55,45" fill="#3A9BE0"/>'
  +   '<path d="M15 23l8 4.6" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity=".9"/>'
  +   '<path d="M14.5 34.5v7" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity=".7"/>'
  +   '<path d="M32 31v28M9 18l23 13 23-13" fill="none" stroke="#1E78C0" stroke-width="1.8" stroke-linejoin="round" opacity=".7"/>'
  +   '<path d="M32 5l23 13v27L32 59 9 45V18z" fill="none" stroke="#1E78C0" stroke-width="2.6" stroke-linejoin="round"/>'
  + '</symbol>'
  + '<symbol id="ic-fast" viewBox="0 0 64 64">'
  +   '<rect width="64" height="64" rx="14" fill="#123645"/>'
  +   '<path d="M10 28c0-11 10-18 22-18s22 7 22 18z" fill="#f2a93b"/>'
  +   '<circle cx="24" cy="20" r="1.8" fill="#fde9bd"/><circle cx="33" cy="16" r="1.8" fill="#fde9bd"/><circle cx="41" cy="22" r="1.8" fill="#fde9bd"/>'
  +   '<path d="M8 30h48l-4 4-4-3-4 3-4-3-4 3-4-3-4 3-4-3-4 3-4-3z" fill="#6cc04a"/>'
  +   '<rect x="9" y="35" width="46" height="8" rx="4" fill="#6b3a1e"/>'
  +   '<path d="M10 46h44v2c0 5-4 8-9 8H19c-5 0-9-3-9-8z" fill="#f2a93b"/>'
  + '</symbol>'
  + '</svg>';

function smInjectSprite(){
  if(document.getElementById('sm-sprite')) return;
  const holder = document.createElement('div');
  holder.id = 'sm-sprite';
  holder.innerHTML = SM_SPRITE;
  document.body.insertBefore(holder, document.body.firstChild);
}

function iconSvg(id, cls){
  return `<svg class="ic ${cls || ''}" viewBox="0 0 64 64" aria-hidden="true" focusable="false"><use href="#${id}"></use></svg>`;
}

/* ---------- Small helpers ---------- */
function escHtml(str){
  return String(str == null ? '' : str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function setStorage(name, value){
  try{
    localStorage.setItem(name, value);
    return true;
  }catch(err){
    console.warn(`Could not save "${name}" to this browser's storage.`, err);
    return false;
  }
}
function getStorage(name){
  try{ return localStorage.getItem(name); }catch(err){ return null; }
}
function removeStorage(name){
  try{ localStorage.removeItem(name); }catch(err){}
}

// Browser-storage keys (planner <-> product list hand-off, saved weeks, form).
const STORE = {
  savedWeeks: 'singleManSavedWeeks',
  currentWeek: 'singleManCurrentWeek',
  formData: 'singleManFormData',
  pickRequest: 'singleManPickRequest',
  pickResult: 'singleManPickResult'
};

/* ---------- FROZEN pool: which items are breakfast / healthy / vegetarian ---------- */
// Brand/keyword-based diet filters. "Healthy" = a recognized portion-controlled
// diet-brand line (brand only, no keyword guessing). "Vegetarian" = a recognized
// all-vegetarian brand OR the name itself says so via a keyword -- checked
// against this pool's actual product names, deliberately excluding "veggie" and
// "dairy free", both of which false-positive against real meat items here (e.g.
// "Bacon, Ham & Veggies Frittata", "Cauliflower, Cheese & Bacon Veggie Tots").
const HEALTHY_BRANDS = ['lean cuisine', 'healthy choice', 'smart ones', 'life cuisine', 'atkins', 'realgood foods co.', 'caulipower', 'birdseye', 'birds eye voila', 'garden lites', 'garden lites veggies made great', 'kodiak', 'kodiak cakes', 'quest nutrition', "kevin's natural foods", "kevin's",
  // Added after checking the pool's top brands against dietitian "healthy frozen
  // meal" roundups: Amy's (both spellings in the pool), plus Evol, Saffron Road
  // and Green Giant.
  "amy's kitchen", "amy's", 'evol', 'saffron road', 'green giant'];
// Name-level healthy signal for a specific line within a brand that isn't
// otherwise a "healthy" brand overall (Jimmy Dean's regular lineup is not),
// plus a blanket "protein" callout -- if the product itself advertises its
// protein content in the name, treat that as a healthy signal.
// "jimmy dean delights" is Jimmy Dean's lighter egg-white/turkey-sausage line;
// it has to be the full phrase since plain "delights" also matches unrelated
// products (e.g. Caribbean Food Delights beef patties).
const HEALTHY_KEYWORDS = ['simple scrambles', 'jimmy dean delights', 'protein', 'organic'];
// Cheese sticks are never "healthy" -- not even when the name carries a healthy
// keyword (e.g. Farm Rich's "High Protein Snack" mozzarella sticks). They ARE
// treated as vegetarian below.
const CHEESE_STICK_KEYWORDS = ['cheese stick', 'mozzarella stick'];
const VEGETARIAN_BRANDS = ["amy's kitchen", 'beyond meat', 'daiya'];
const VEGETARIAN_KEYWORDS = ['vegetarian', 'vegan', 'plant based', 'plant-based', 'meatless'];

// Dish types that are vegetarian by default UNLESS a meat word also shows up in
// the name -- pancakes/waffles/muffins/bread/pasta/pizza all have plenty of
// plain cheese/veggie versions in this pool, so rather than keyword-whitelist
// every product we whitelist the dish type and blacklist meat mentions.
const VEG_DISH_KEYWORDS = ['pancake', 'flapjack', 'waffle', 'muffin', 'bread', 'breadstick', 'texas toast',
  'pasta', 'fettuccine', 'fettucine', 'fettuccini', 'alfredo', 'spaghetti', 'lasagna', 'ravioli',
  'linguine', 'penne', 'rigatoni', 'ziti', 'noodle', 'mac & cheese', 'mac and cheese', 'macaroni',
  'tortellini', 'gnocchi', 'cavatelli', 'pizza', 'burrito'];
const MEAT_WORDS = ['chicken', 'beef', 'pork', 'saus', 'bacon', 'shrimp', 'turkey', 'ham', 'steak', 'meat', 'chili',
  'pepperoni', 'fish', 'salmon', 'tuna', 'sirloin', 'anchov', 'prosciutto', 'salami',
  'chorizo', 'pastrami', 'brisket', 'rib', 'wing', 'lamb', 'seafood', 'crawfish', 'haddock', 'calamari',
  'scallop', 'boudin', 'veal', 'venison', 'duck', 'crab', 'clam', 'oyster',
  // Spanish meat names -- burritos are the dish type these tend to show up on.
  'carne', 'pollo', 'barbacoa', 'machaca', 'al pastor'];
// Pizza-topping code words -- these only signal meat on an actual pizza (a
// "Supreme" or "Hawaiian" pizza is pepperoni/sausage/ham by convention; a
// "Mexican Style" pizza is taco-seasoned beef/sausage). Off a pizza they mean
// nothing ("Hawaiian Bread" is just sweet bread), so this list is only checked
// when the item is also a pizza.
const PIZZA_MEAT_CODE_WORDS = ['supreme', 'combination', 'combo', 'hawaiian', 'deluxe', 'mexican'];

// Which pool an item belongs to. Breakfast = the "Frozen Breakfast" category,
// "breakfast" anywhere in the name, ANY Jimmy Dean product, or a waffle /
// french toast / pancake dish (flapjacks are pancakes). Waffle-cut fries share
// the word "waffle" but are a side dish, so they stay in the general pool.
const BREAKFAST_BRANDS = ['jimmy dean'];
const BREAKFAST_DISH_KEYWORDS = ['waffle', 'french toast', 'pancake', 'flapjack'];
const NOT_BREAKFAST_KEYWORDS = ['waffle cut', 'waffle fries'];

function frozenIsBreakfast(item){
  const name = (item.PRODUCT_NAME || item.name || '').toLowerCase();
  if(item.CATEGORY === 'Frozen Breakfast' || item.category === 'Frozen Breakfast') return true;
  if(name.includes('breakfast')) return true;
  if(BREAKFAST_BRANDS.includes(frozenBrandKey(item)) || name.includes('jimmy dean')) return true;
  if(NOT_BREAKFAST_KEYWORDS.some(kw => name.includes(kw))) return false;
  return BREAKFAST_DISH_KEYWORDS.some(kw => name.includes(kw));
}

function frozenBrandKey(meal){
  return (meal.BRAND || meal.brand || '').trim().toLowerCase();
}

function isCheeseStick(name){
  return CHEESE_STICK_KEYWORDS.some(kw => name.includes(kw));
}

function frozenIsHealthy(meal){
  const name = (meal.PRODUCT_NAME || meal.name || '').toLowerCase();
  if(isCheeseStick(name)) return false;
  if(HEALTHY_BRANDS.includes(frozenBrandKey(meal))) return true;
  return HEALTHY_KEYWORDS.some(kw => name.includes(kw));
}

function frozenIsVegetarian(meal){
  if(VEGETARIAN_BRANDS.includes(frozenBrandKey(meal))) return true;
  const name = (meal.PRODUCT_NAME || meal.name || '').toLowerCase();
  if(VEGETARIAN_KEYWORDS.some(kw => name.includes(kw))) return true;
  if(isCheeseStick(name) && !MEAT_WORDS.some(w => name.includes(w))) return true;

  const isDish = VEG_DISH_KEYWORDS.some(kw => name.includes(kw));
  if(!isDish) return false;
  // A "burrito bowl" doesn't tell you what's in it (e.g. "Unwrapped Burrito
  // Bowl" with no protein named), and "burrito tortillas" is a bag of wraps, not
  // a burrito -- only a named burrito with no meat word (bean & cheese, egg &
  // cheese, ...) is treated as vegetarian.
  if(name.includes('burrito bowl') || name.includes('tortilla')) return false;
  const hasMeatWord = MEAT_WORDS.some(w => name.includes(w));
  if(hasMeatWord) return false;
  const isPizza = name.includes('pizza');
  if(isPizza && PIZZA_MEAT_CODE_WORDS.some(w => name.includes(w))) return false;
  return true;
}



/* ---------- FAST FOOD pool: Gemini sets the "healthy" / "vegetarian" flags per meal ---------- */
// Pizza is never healthy; tacos aren't either unless they're street-style / Fresco, or Chipotle's or Qdoba's.
function fastIsHealthy(meal){
  if(meal.healthy !== true) return false;
  const name = String(meal.PRODUCT_NAME || meal.name || '');
  if(/\bpizzas?\b/i.test(name)) return false;
  const brand = String(meal.restaurant || meal.BRAND || '');
  if(/\btacos?\b/i.test(name) && !(/\bstreet\b|\bfresco\b/i.test(name) || ['Chipotle', 'Qdoba'].includes(brand))) return false;
  return true;
}
function fastIsVegetarian(meal){
  return meal.vegetarian === true;
}

/* ---------- Common item shape ---------- */
function getMealSource(meal){
  return meal.source || (meal.restaurant ? 'fast' : 'frozen');
}

function isHealthyMeal(meal){
  return getMealSource(meal) === 'fast' ? fastIsHealthy(meal) : frozenIsHealthy(meal);
}
function isVegetarianMeal(meal){
  return getMealSource(meal) === 'fast' ? fastIsVegetarian(meal) : frozenIsVegetarian(meal);
}

// candidate_pool.json row -> planner item (the row itself, tagged in place to save memory).
function normalizeFrozenItem(raw){
  raw.source = 'frozen';
  raw._cat = frozenIsBreakfast(raw) ? 'breakfast' : 'regular';
  return raw;
}

// meals.json entry -> planner item.
function normalizeFastItem(m){
  const cat = m.category === 'breakfast' ? 'breakfast' : (m.category === 'dessert' ? 'dessert' : 'regular');
  return {
    source: 'fast',
    _cat: cat,
    PRODUCT_NAME: m.name,
    BRAND: m.restaurant,
    restaurant: m.restaurant,
    CATEGORY: cat === 'breakfast' ? 'Breakfast' : (cat === 'dessert' ? 'Dessert' : 'Regular'),
    calories: m.calories,
    PRICE_CURRENT: m.price,
    servings_per_container: m.serving,
    vegetarian: m.vegetarian === true,
    healthy: fastIsHealthy({ healthy: m.healthy, name: m.name, restaurant: m.restaurant }),
    image_url: m.image_url || '',
    image_full_url: m.image_full_url || '',
    active: m.active,
    _added_at: m._added_at || '',
    _updated_at: m._updated_at || ''
  };
}

function getMealName(meal){ return meal.PRODUCT_NAME || meal.name || 'Unnamed item'; }
// Fast food items belong to a restaurant; frozen items just have a brand that is already in the product name.
function getMealRestaurant(meal){
  return getMealSource(meal) === 'fast' ? String(meal.restaurant || meal.BRAND || '').trim() : '';
}
function getMealCategory(meal){ return meal._cat || meal.cat || 'regular'; }

function getMealCalories(meal){
  if(typeof meal.calories === 'number') return meal.calories;
  if(meal.calories && !isNaN(Number(meal.calories))) return Number(meal.calories);
  if(meal.open_food_facts && typeof meal.open_food_facts.calories === 'number'){
    return meal.open_food_facts.calories;
  }
  return 0;
}

function getMealServing(meal){
  if(meal.SERVINGS_PER_CONTAINER) return meal.SERVINGS_PER_CONTAINER;
  if(meal.servings_per_container) return meal.servings_per_container;
  if(meal.serving) return meal.serving;
  if(meal.servings) return meal.servings;
  if(meal.open_food_facts && meal.open_food_facts.servings_per_container){
    return meal.open_food_facts.servings_per_container;
  }
  return 'N/A';
}

function getMealPrice(meal){
  const price = meal.PRICE_CURRENT ?? meal.price ?? meal.PRICE_RETAIL;
  if(price === undefined || price === null || price === 0 || price === '0') return 'N/A';
  const num = parseFloat(price);
  return isNaN(num) ? 'N/A' : `$${num.toFixed(2)}`;
}
function getMealPriceNumber(meal){
  const raw = meal.PRICE_CURRENT ?? meal.price ?? meal.PRICE_RETAIL;
  const num = parseFloat(raw);
  return isNaN(num) ? 0 : num;
}

function getMealUrl(meal){
  return meal.PRODUCT_URL || meal.product_url || meal.url || (meal.open_food_facts ? meal.open_food_facts.url : '') || '';
}
function getMealInstacartUrl(meal){
  return meal.INSTACART_URL || meal.instacart_url || meal.instacart || '';
}
function getMealImage(meal){ return meal.image_url || meal.image || ''; }
function getMealImageFallback(meal){ return meal.image_full_url || meal.imageFull || ''; }

/* ---------- Fast food: restaurant websites + delivery-app links ---------- */
// The approved restaurants. meals.json carries this list too and wins when present;
// this copy is only the fallback if it can't be loaded.
let restaurantInfo = [
  "Applebee's", "Arby's", "Blaze Pizza", "Buffalo Wild Wings",
  "Burger King", "Charleys Cheesesteaks", "Cheddar's", "Chick-fil-A",
  "Chili's", "Chipotle", "Cracker Barrel", "Culver's",
  "Dairy Queen", "Denny's", "Domino's", "Dunkin'",
  "Famous Dave's", "Firehouse Subs", "Five Guys", "Freddy's",
  "Godfather's Pizza", "IHOP", "Jersey Mike's Subs", "Jimmy John's",
  "Kentucky Fried Chicken", "Little Caesar's", "Long John Silver's", "McAlister's Deli",
  "McDonald's", "Moe's Southwest Grill", "Noodles & Company", "Olive Garden",
  "Outback Steakhouse", "Panda Express", "Panera", "Papa John's",
  "Papa Murphy's", "Pizza Hut", "Popeyes", "Qdoba",
  "Raising Cane's", "Red Robin", "Slim Chickens", "Sonic Drive-In",
  "Starbucks", "Subway", "Taco Bell", "Texas Roadhouse",
  "Wendy's", "Wingstop"
];

// Each restaurant's official website (meals.json carries these too and wins when present).
// The site's favicon is shown before the delivery-app icons and links there.
let restaurantSites = {
  "Applebee's": "www.applebees.com", "Arby's": "www.arbys.com",
  "Blaze Pizza": "www.blazepizza.com", "Buffalo Wild Wings": "www.buffalowildwings.com",
  "Burger King": "www.bk.com", "Charleys Cheesesteaks": "www.charleys.com",
  "Cheddar's": "www.cheddars.com", "Chick-fil-A": "www.chick-fil-a.com",
  "Chili's": "www.chilis.com", "Chipotle": "www.chipotle.com",
  "Cracker Barrel": "www.crackerbarrel.com", "Culver's": "www.culvers.com",
  "Dairy Queen": "www.dairyqueen.com", "Denny's": "www.dennys.com",
  "Domino's": "www.dominos.com", "Dunkin'": "www.dunkindonuts.com",
  "Famous Dave's": "www.famousdaves.com", "Firehouse Subs": "www.firehousesubs.com",
  "Five Guys": "www.fiveguys.com", "Freddy's": "www.freddys.com",
  "Godfather's Pizza": "www.godfathers.com", "IHOP": "www.ihop.com",
  "Jersey Mike's Subs": "www.jerseymikes.com", "Jimmy John's": "www.jimmyjohns.com",
  "Kentucky Fried Chicken": "www.kfc.com", "Little Caesar's": "www.littlecaesars.com",
  "Long John Silver's": "www.ljsilvers.com", "McAlister's Deli": "www.mcalistersdeli.com",
  "McDonald's": "www.mcdonalds.com", "Moe's Southwest Grill": "www.moes.com",
  "Noodles & Company": "www.noodles.com", "Olive Garden": "www.olivegarden.com",
  "Outback Steakhouse": "www.outback.com", "Panda Express": "www.pandaexpress.com",
  "Panera": "www.panerabread.com", "Papa John's": "www.papajohns.com",
  "Papa Murphy's": "www.papamurphys.com", "Pizza Hut": "www.pizzahut.com",
  "Popeyes": "www.popeyes.com", "Qdoba": "www.qdoba.com",
  "Raising Cane's": "www.raisingcanes.com", "Red Robin": "www.redrobin.com",
  "Slim Chickens": "www.slimchickens.com", "Sonic Drive-In": "www.sonicdrivein.com",
  "Starbucks": "www.starbucks.com", "Subway": "www.subway.com",
  "Taco Bell": "www.tacobell.com", "Texas Roadhouse": "www.texasroadhouse.com",
  "Wendy's": "www.wendys.com", "Wingstop": "www.wingstop.com"
};

// Links after the select/regen buttons: the restaurant's own website (its favicon) first,
// then the delivery apps, whose search URLs get the restaurant name. Only favicons are shown
// (the name is in the tooltip / screen-reader label); they are squeezed tightly together.
function siteLinkHtml(restaurant, stopClick){
  const site = String(restaurantSites[restaurant] || '').trim();
  if(!/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(site)) return '';
  const label = `${restaurant} website`;
  const stop = stopClick ? ' onclick="event.stopPropagation()"' : '';
  return `<a class="deliv deliv-site" href="https://${site}/" target="_blank" rel="noopener noreferrer" title="${escHtml(label)}" aria-label="${escHtml(label)}"${stop}><img class="deliv-ic" src="https://www.google.com/s2/favicons?domain=${site}&sz=64" alt="" width="20" height="20" loading="lazy" referrerpolicy="no-referrer" /><span aria-hidden="true">&rarr;</span></a>`;
}

function deliveryIconsHtml(restaurant, stopClick){
  const query = encodeURIComponent(restaurant);
  const stop = stopClick ? ' onclick="event.stopPropagation()"' : '';
  const apps = [
    ['doordash.com', 'DoorDash',  `https://www.doordash.com/search/store/${query}/`],
    ['ubereats.com', 'Uber Eats', `https://www.ubereats.com/search?q=${query}`],
    ['grubhub.com', 'Grubhub',   `https://www.grubhub.com/search?queryText=${query}`]
  ];
  return siteLinkHtml(restaurant, stopClick) + apps.map(([domain, label, url]) =>
    `<a class="deliv" href="${url}" target="_blank" rel="noopener noreferrer" title="Search ${label}" aria-label="Search ${label}"${stop}><img class="deliv-ic" src="https://www.google.com/s2/favicons?domain=${domain}&sz=64" alt="" width="20" height="20" loading="lazy" referrerpolicy="no-referrer" /><span aria-hidden="true">&rarr;</span></a>`
  ).join('');
}

/* ---------- Frozen: Walmart / Instacart chips ---------- */
// prefix is "meal" (planner tiles) or "prod" (product list); the matching CSS lives in each page.
function retailerChipsHtml(meal, prefix, missingPlaceholders){
  const url = getMealUrl(meal);
  const instacartUrl = getMealInstacartUrl(meal);
  const chip = (href, key, label, host) => href
    ? `<a class="${prefix}-link ${prefix}-link-${key}" href="${escHtml(href)}" target="_blank" rel="noopener noreferrer" title="${host === 'walmart.com' ? 'Search' : 'View on'} ${host}"><span class="${prefix}-link-name"><span class="sr-only">${host === 'walmart.com' ? 'Search ' : 'View on '}</span>${label} &rarr;</span></a>`
    : (missingPlaceholders ? `<span class="${prefix}-link-missing">no ${label} link</span>` : '');
  return chip(url, 'walmart', 'Walmart', 'walmart.com') + chip(instacartUrl, 'instacart', 'Instacart', 'Instacart');
}

/* ---------- Dates for the footnote ---------- */
function parseDataTimestamp(raw){
  if(!raw || typeof raw !== 'string') return NaN;
  // "2022-09-11 21:20:04" -> ISO (Safari needs the T); trim microseconds to ms.
  const iso = raw.trim().replace(' ', 'T').replace(/(\.\d{3})\d+/, '$1');
  return Date.parse(iso);
}
function latestDataDate(items, fields){
  let newest = NaN;
  items.forEach(item => {
    fields.forEach(field => {
      const t = parseDataTimestamp(item[field]);
      if(!isNaN(t) && (isNaN(newest) || t > newest)) newest = t;
    });
  });
  return isNaN(newest) ? null : new Date(newest);
}
// Newest timestamp anywhere in the frozen pool's price/calorie bookkeeping: the original
// scrape date (RunDate) or any later refresh (calorie check, Gemini lookup, Kroger
// discovery). Image-only checks are deliberately excluded.
const FROZEN_DATA_DATE_FIELDS = ['RunDate', '_calorie_max_checked_at', '_gemini_checked_at', '_kroger_discovered_at'];
const FAST_DATA_DATE_FIELDS = ['_added_at', '_updated_at'];
