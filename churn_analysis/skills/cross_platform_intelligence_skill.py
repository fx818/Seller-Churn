"""Cross-platform intelligence skill.

Flow:
  1. Enrich seller via IndiaMART getContext API (company name, GST, email domain)
  2. Requests-based: JustDial __NEXT_DATA__ JSON → company found, rating, reviews, profile URL
  3. Playwright: visit JustDial profile + TradeIndia + own website → product counts
"""

import os
import re
import json
import time
from urllib.parse import quote

import requests

from .base_skill import Skill, SkillResult

_REQ_TIMEOUT  = int(os.getenv("CPPI_REQ_TIMEOUT_S", "12"))
_PW_TIMEOUT   = int(os.getenv("CPPI_PW_TIMEOUT_MS", "18000"))
_USER_AGENT   = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_GENERIC_DOMAINS = {
    "gmail.com", "yahoo.com", "yahoo.in", "hotmail.com", "rediffmail.com",
    "outlook.com", "indiamart.com", "justdial.com", "tradeindia.com",
}

_IM_EMPID = os.getenv("IM_EMPID", "")
_IM_JWT   = os.getenv("IM_INTERNAL_JWT", "")

_GEN_UID_URL = "https://merp.intermesh.net/go/api/globalcontext/v1/generateContextUID"
_GET_CTX_URL = "https://merp.intermesh.net/go/api/globalcontext/v1/x/getContext"


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": _USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    })
    return s


def _fetch_context(glid) -> dict:
    if not _IM_EMPID or not _IM_JWT:
        return {}
    try:
        uid = requests.post(
            _GEN_UID_URL,
            json={"mapping_type": 1, "mapping_value": str(glid), "source_id": 1,
                  "empid": int(_IM_EMPID), "ak": _IM_JWT, "data_segments": "all"},
            timeout=_REQ_TIMEOUT, headers={"User-Agent": _USER_AGENT},
        )
        if uid.status_code != 200:
            return {}
        mid = uid.json().get("data", {}).get("mapping_id", "")
        if not mid:
            return {}
        ctx = requests.get(_GET_CTX_URL, params={"mapping_id": mid, "data_keys": "all"},
                           timeout=_REQ_TIMEOUT, headers={"User-Agent": _USER_AGENT})
        if ctx.status_code != 200:
            return {}
        kyc = ctx.json().get("data", {}).get("kycdetails", {})
        return kyc if isinstance(kyc, dict) else {}
    except Exception:
        return {}


def _extract_hints(ctx: dict, company: str, city: str) -> dict:
    catalog_url = ctx.get("catalog_url", "")
    im_alias = ctx.get("freeshowroom_alias_im", "")
    if not im_alias and catalog_url:
        m = re.search(r"indiamart\.com/([^/]+)", catalog_url)
        if m:
            im_alias = m.group(1)
    email = ctx.get("email1", "")
    email_domain = email.split("@")[1].lower() if "@" in email else ""
    return {
        "company_name":      ctx.get("company_name") or company,
        "city":              ctx.get("city") or city,
        "address":           ctx.get("address", ""),
        "gst":               ctx.get("gst_new", ""),
        "email_domain":      email_domain,
        "im_alias":          im_alias,
        "approved_products": int(ctx.get("approved_product_count") or 0),
        "catalog_url":       catalog_url,
    }


def _to_slug(text: str) -> str:
    return "-".join(re.sub(r"[^a-zA-Z0-9\s]", "", text).strip().split())


def _name_score(company: str, text: str) -> float:
    words = [w.lower() for w in company.split() if len(w) > 2]
    if not words:
        return 0.0
    tl = text.lower()
    return sum(1 for w in words if w in tl) / len(words)


def _extract_number(text: str, keyword: str) -> int:
    """Find a number near a keyword. Tries multiple patterns:
       "24 Products", "Products: 24", "Products (24)", "Products 24",
       "Showing 1-12 of 24", "All 24 Products".
    """
    if not text or not keyword:
        return 0
    kw = re.escape(keyword)
    patterns = [
        rf"(\d[\d,]*)\s*{kw}",                                # "24 Products"
        rf"{kw}\s*[:\-]?\s*\(?\s*(\d[\d,]*)\s*\)?",           # "Products: 24" / "Products (24)"
        rf"{kw}\s+(\d[\d,]*)",                                # "Products 24"
        rf"showing\s+\d+\s*[-–to]+\s*\d+\s+of\s+(\d[\d,]*)",  # "Showing 1-12 of 24"
        rf"all\s+(\d[\d,]*)\s+{kw}",                          # "All 24 Products"
        rf"view\s+all\s*\(?\s*(\d[\d,]*)\s*\)?",              # "View All (24)"
        rf"total\s+(\d[\d,]*)\s+{kw}",                        # "Total 24 Products"
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                n = int(m.group(1).replace(",", ""))
                if 0 < n < 10000:        # sanity bound
                    return n
            except (ValueError, IndexError):
                continue
    return 0


def _extract_any_count(text: str, keywords: list[str]) -> int:
    """Try a list of keywords, return the largest plausible count found."""
    best = 0
    for kw in keywords:
        n = _extract_number(text, kw)
        if 0 < n < 10000 and n > best:
            best = n
    return best


def _wait(page, ms=1500):
    try:
        page.wait_for_timeout(ms)
    except Exception:
        time.sleep(ms / 1000)


def _page_text(page) -> str:
    try:
        return page.inner_text("body") or ""
    except Exception:
        try:
            return page.evaluate("document.body.innerText") or ""
        except Exception:
            return ""


def _goto(page, url: str) -> bool:
    for wait in ("domcontentloaded", "networkidle"):
        try:
            page.goto(url, wait_until=wait, timeout=_PW_TIMEOUT)
            return True
        except Exception:
            pass
    return False


# ── Phase 1: requests-based JustDial discovery ──────────────────────────────

def _jd_discover(hints: dict, sess: requests.Session) -> dict:
    """Find company on JustDial via __NEXT_DATA__ JSON. Returns basic info + profile URL."""
    empty = {"found": False, "product_count": 0, "photo_count": 0,
             "rating": 0.0, "reviews": 0, "categories": [], "url": ""}

    company   = hints["company_name"]
    city      = hints["city"]
    slug      = _to_slug(company)
    city_slug = _to_slug(city) if city else ""

    urls = []
    if city_slug:
        urls += [
            f"https://www.justdial.com/{city_slug}/{slug}/",
            f"https://www.justdial.com/{city_slug}/{'-'.join(slug.split('-')[:3])}/",
            f"https://www.justdial.com/{city_slug}/{quote(company)}/",
        ]
    urls += [
        f"https://www.justdial.com/{slug}/",
        f"https://www.justdial.com/{quote(company)}/",
    ]

    for url in urls:
        try:
            r = sess.get(url, timeout=_REQ_TIMEOUT, allow_redirects=True)
            if r.status_code != 200 or len(r.text) < 500:
                continue
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
            if not m:
                continue
            data = json.loads(m.group(1))
            list_data = (data.get("props", {}).get("pageProps", {})
                             .get("listData", {}).get("results", {}))
            columns = list_data.get("columns", [])
            rows    = list_data.get("data", [])
            if not columns or not rows:
                continue

            col_idx = {c: i for i, c in enumerate(columns)}

            def _get(row, col):
                idx = col_idx.get(col)
                return row[idx] if idx is not None and idx < len(row) else None

            best_row, best_score = None, 0.0
            for row in rows:
                score = _name_score(company, _get(row, "name") or "")
                if score > best_score:
                    best_score, best_row = score, row

            if best_row is None or best_score < 0.4:
                continue

            name = _get(best_row, "name") or company
            try:
                rating = float(_get(best_row, "compRating") or 0)
            except (TypeError, ValueError):
                rating = 0.0

            rev_raw = str(_get(best_row, "totalReviews") or "")
            rev_m = re.search(r"(\d+)", rev_raw)
            reviews = int(rev_m.group(1)) if rev_m else 0

            sharedt = _get(best_row, "sharedt_url") or ""
            weburl  = _get(best_row, "weburl") or ""
            if sharedt and sharedt.startswith("http"):
                profile_url = sharedt
            elif weburl:
                profile_url = (f"https://www.justdial.com/{weburl}"
                               if not weburl.startswith("http") else weburl)
            else:
                profile_url = url

            ev           = _get(best_row, "event_data") or {}
            sc           = _get(best_row, "service_catalog") or []
            ev_svc       = int(ev.get("services") or 0)
            sc_count     = len(sc) if isinstance(sc, list) else 0
            price_count  = int(ev.get("price_count") or 0)
            dimages      = _get(best_row, "dimages") or []
            dimages_cnt  = len(dimages) if isinstance(dimages, list) else 0
            photocnt     = int(_get(best_row, "photocnt") or 0)
            # Fallback chain: structured catalog → service catalog → price entries
            # → catalog images (dimages) → photo count. JustDial often has zero
            # in the first three but real entries in `dimages` for small sellers.
            product_count = ev_svc or sc_count or price_count or dimages_cnt or photocnt
            catalog_flag = str(ev.get("catalog_flag") or _get(best_row, "catalog_flag") or "0")

            nwtaglin   = _get(best_row, "nwtaglin") or []
            area       = _get(best_row, "area") or ""
            categories = list(nwtaglin[:3]) + ([area] if area and area not in nwtaglin else [])

            return {
                "found":          True,
                "name_matched":   name,
                "product_count":  product_count,
                "photo_count":    photocnt,
                "catalog_items":  dimages_cnt,
                "catalog_flag":   catalog_flag == "1",
                "rating":         rating,
                "reviews":        reviews,
                "categories":     [c for c in categories if c][:4],
                "url":            profile_url,
                "match_score":    round(best_score, 2),
            }
        except Exception:
            continue

    return empty


# ── Phase 2: Playwright product count extraction ─────────────────────────────

_PRODUCT_TEXT_KEYWORDS = [
    "Products", "Services", "Items", "Catalogue", "Catalog",
    "Product Listing", "Product Range", "Our Products",
    "products", "services", "items",
]


def _autoscroll(page, max_scrolls: int = 6, step_px: int = 1200) -> None:
    """Scroll to bottom to trigger lazy-loaded product cards."""
    try:
        last_h = page.evaluate("document.body.scrollHeight")
        for _ in range(max_scrolls):
            page.evaluate(f"window.scrollBy(0, {step_px})")
            page.wait_for_timeout(700)
            h = page.evaluate("document.body.scrollHeight")
            if h == last_h:
                break
            last_h = h
        page.evaluate("window.scrollTo(0, 0)")
    except Exception:
        pass


def _count_jsonld_products(page) -> int:
    """Look for JSON-LD schema with Product / ItemList markup."""
    try:
        scripts = page.query_selector_all('script[type="application/ld+json"]')
        total = 0
        for s in scripts:
            try:
                raw = s.inner_text() or s.text_content() or ""
                if not raw.strip():
                    continue
                data = json.loads(raw)
            except Exception:
                continue
            items = data if isinstance(data, list) else [data]
            for it in items:
                if not isinstance(it, dict):
                    continue
                t = it.get("@type") or it.get("type") or ""
                if isinstance(t, list):
                    t = ",".join(t)
                # ItemList → numberOfItems or itemListElement
                if "ItemList" in str(t):
                    n = it.get("numberOfItems")
                    if isinstance(n, (int, float)) and n > 0:
                        return int(n)
                    elements = it.get("itemListElement") or []
                    if isinstance(elements, list) and elements:
                        total += len(elements)
                # OfferCatalog
                elif "OfferCatalog" in str(t):
                    offers = it.get("itemListElement") or []
                    if isinstance(offers, list):
                        total += len(offers)
                # Bare Product entries
                elif "Product" in str(t):
                    total += 1
        return total
    except Exception:
        return 0


def _count_via_js_heuristics(page) -> int:
    """Use page.evaluate to find repeating card-like structures.

       Strategies inside the browser:
         1. Count anchors whose href contains /product, /catalog, /catalogue, /item, /service
         2. Count direct children of grid/flex containers that have >=4 similar siblings
         3. Count <img> tags inside common catalogue containers with product-shaped src
    """
    js = """
    () => {
      const counts = [];

      // 1. Product-like anchors
      const productHrefRe = /\\/(product|products|catalogue|catalog|item|items|service|services|prod)[\\/_-]/i;
      const anchors = Array.from(document.querySelectorAll('a[href]'));
      const productAnchors = new Set();
      for (const a of anchors) {
        const href = a.getAttribute('href') || '';
        if (productHrefRe.test(href) && href.length < 400) {
          // normalize trailing slash + querystring
          productAnchors.add(href.split('?')[0].replace(/\\/+$/, ''));
        }
      }
      if (productAnchors.size > 0) counts.push(productAnchors.size);

      // 2. Grid children that look uniform
      const containerSel = [
        '[class*="product"]', '[class*="catalog"]', '[class*="catalogue"]',
        '[class*="grid"]', '[class*="listing"]', '[id*="product"]', '[id*="catalog"]'
      ].join(',');
      const containers = Array.from(document.querySelectorAll(containerSel));
      for (const c of containers) {
        const kids = Array.from(c.children).filter(k => k.tagName !== 'SCRIPT' && k.tagName !== 'STYLE');
        if (kids.length >= 3 && kids.length < 500) {
          // require uniform tag (e.g. all LI / all DIV) AND similar class
          const tags = new Set(kids.map(k => k.tagName));
          if (tags.size === 1) {
            const klass = kids[0].className || '';
            const sameClass = kids.filter(k => (k.className || '') === klass).length;
            if (sameClass >= 3) counts.push(sameClass);
          }
        }
      }

      // 3. Distinct product images
      const productImgRe = /(product|catalog|catalogue|prod|item|service)/i;
      const imgs = Array.from(document.querySelectorAll('img'));
      const productImgs = new Set();
      for (const img of imgs) {
        const src = img.getAttribute('src') || img.getAttribute('data-src') || '';
        if (src && productImgRe.test(src)) {
          productImgs.add(src.split('?')[0]);
        }
      }
      if (productImgs.size > 1) counts.push(productImgs.size);

      // Return the most common plausible value (not the max, not the min)
      if (counts.length === 0) return 0;
      counts.sort((a, b) => a - b);
      // Pick the median to be robust against outliers
      return counts[Math.floor(counts.length / 2)];
    }
    """
    try:
        n = page.evaluate(js)
        return int(n or 0)
    except Exception:
        return 0


def _count_via_css_selectors(page) -> int:
    """Fallback: try a broader set of CSS selectors for product cards."""
    product_selectors = [
        "[class*='product-item']", "[class*='product-card']",
        "[class*='ProductCard']", "[class*='product_item']",
        "[class*='catalogue-item']", "[class*='catalog-item']",
        "[class*='catalog-card']", "[class*='catalogue-card']",
        ".product", ".prod-item", ".item-card",
        "[class*='listing-item']", "[class*='product-list'] > li",
        "[class*='product-list'] > div",
        ".grid-item", "[class*='prd-box']",
        "[data-testid*='product']", "[data-test*='product']",
        "[class*='cat-item']", "[class*='prd-card']",
        "[class*='service-list'] > li", "[class*='serv-list'] > li",
        "ul[class*='product'] > li", "div[class*='product-grid'] > div",
    ]
    counts = []
    for sel in product_selectors:
        try:
            items = page.query_selector_all(sel)
            if 2 <= len(items) < 500:
                counts.append(len(items))
        except Exception:
            pass
    if not counts:
        return 0
    counts.sort()
    # median is more robust than max (one bad selector can match the whole nav)
    return counts[len(counts) // 2]


# ── Title extraction + fuzzy matching ───────────────────────────────────────

_TITLE_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "for", "with", "in", "on",
    "by", "to", "from", "at", "is", "are", "this", "that", "our",
    "we", "us", "you", "your", "best", "high", "quality", "premium",
    "wholesale", "retail", "supplier", "manufacturer", "exporter",
    "trader", "company", "online", "offer", "buy", "sale", "new",
    "pack", "set", "piece", "pcs", "kg", "gm", "mg", "ml", "ltr",
    "inch", "cm", "mm", "ft", "size", "model", "type", "grade",
    "indian", "india",
}

_UNIT_RE  = re.compile(r"\b\d+(?:\.\d+)?\s*(?:kg|gm|g|mg|ml|l|ltr|cm|mm|m|inch|ft|pcs|pc|piece|pack|set|hp|kw|watt|w|v|amp|ah|rpm)\b", re.IGNORECASE)
_PUNCT_RE = re.compile(r"[^\w\s]")
_WS_RE    = re.compile(r"\s+")


def _normalize_title(s: str) -> str:
    if not s:
        return ""
    s = s.lower().strip()
    s = _UNIT_RE.sub(" ", s)
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


def _title_tokens(s: str) -> set:
    n = _normalize_title(s)
    if not n:
        return set()
    return {t for t in n.split() if len(t) >= 3 and t not in _TITLE_STOPWORDS}


def _title_similar(a: str, b: str, threshold: float = 0.6) -> bool:
    """Jaccard token overlap >= threshold OR one is a substring of the other."""
    ta, tb = _title_tokens(a), _title_tokens(b)
    if not ta or not tb:
        return False
    inter = ta & tb
    union = ta | tb
    jaccard = len(inter) / len(union) if union else 0.0
    if jaccard >= threshold:
        return True
    # Substring containment (handles "LED Bulb 9W" vs "LED Bulb")
    na = _normalize_title(a)
    nb = _normalize_title(b)
    if na and nb and (na in nb or nb in na) and min(len(na), len(nb)) >= 6:
        return True
    return False


def _dedupe_across_platforms(titles_by_platform: dict) -> dict:
    """Cluster matching products across platforms.

    Returns:
      {
        "clusters":         [[("platform", "title"), ...], ...],
        "unique_count":     int  (number of distinct products across all platforms),
        "overlap_pairs":    [("p1","p2", overlap_count), ...],
        "per_platform_unique": {platform: count of titles not matched anywhere else},
      }
    """
    # Flatten to (platform, title) entries
    entries = []
    for platform, titles in titles_by_platform.items():
        for t in titles or []:
            if t and len(t) >= 3:
                entries.append((platform, t))

    if not entries:
        return {"clusters": [], "unique_count": 0, "overlap_pairs": [],
                "per_platform_unique": {}}

    # Greedy clustering by similarity to cluster head
    clusters: list = []
    for ent in entries:
        placed = False
        for cl in clusters:
            head_title = cl[0][1]
            if _title_similar(ent[1], head_title):
                cl.append(ent)
                placed = True
                break
        if not placed:
            clusters.append([ent])

    # Pairwise overlap counts
    from collections import Counter
    pair_counts: Counter = Counter()
    for cl in clusters:
        platforms_in_cluster = sorted({e[0] for e in cl})
        for i in range(len(platforms_in_cluster)):
            for j in range(i + 1, len(platforms_in_cluster)):
                pair_counts[(platforms_in_cluster[i], platforms_in_cluster[j])] += 1
    overlap_pairs = [(p1, p2, c) for (p1, p2), c in pair_counts.items()]

    # Per-platform unique = titles in clusters that contain ONLY that platform
    per_platform_unique: dict = {p: 0 for p in titles_by_platform.keys()}
    for cl in clusters:
        platforms_in_cluster = {e[0] for e in cl}
        if len(platforms_in_cluster) == 1:
            p = next(iter(platforms_in_cluster))
            per_platform_unique[p] = per_platform_unique.get(p, 0) + 1

    return {
        "clusters":            clusters,
        "unique_count":        len(clusters),
        "overlap_pairs":       overlap_pairs,
        "per_platform_unique": per_platform_unique,
    }


def _pw_extract_titles(page, max_titles: int = 80) -> list:
    """Extract candidate product titles from the page using multiple strategies.

    Order:
      1. JSON-LD Product/ItemList name fields
      2. Anchors with product-like hrefs (use anchor text)
      3. <img alt="..."> for product-shaped src
      4. h2/h3/h4 inside product card containers
    Deduplicates exact-match strings, returns at most max_titles.
    """
    titles: list = []
    seen: set = set()

    def _add(t: str):
        t = (t or "").strip()
        if not t or len(t) < 3 or len(t) > 200:
            return
        key = _normalize_title(t)
        if not key or key in seen:
            return
        seen.add(key)
        titles.append(t)

    # 1. JSON-LD names
    try:
        scripts = page.query_selector_all('script[type="application/ld+json"]')
        for s in scripts:
            try:
                raw  = s.inner_text() or s.text_content() or ""
                data = json.loads(raw) if raw.strip() else None
            except Exception:
                continue
            items = data if isinstance(data, list) else [data]
            for it in items:
                if not isinstance(it, dict):
                    continue
                t = str(it.get("@type") or "")
                if "Product" in t and it.get("name"):
                    _add(str(it["name"]))
                elements = it.get("itemListElement") or []
                if isinstance(elements, list):
                    for el in elements:
                        if isinstance(el, dict):
                            nm = el.get("name") or (el.get("item") or {}).get("name") if isinstance(el.get("item"), dict) else el.get("name")
                            if nm:
                                _add(str(nm))
    except Exception:
        pass

    if len(titles) >= 4:
        return titles[:max_titles]

    # 2 + 3 + 4 via single JS evaluation
    js = """
    () => {
      const out = new Set();
      const productHrefRe = /\\/(product|products|catalogue|catalog|item|items|service|services|prod)[\\/_-]/i;

      // Anchors with product-like hrefs
      for (const a of document.querySelectorAll('a[href]')) {
        const href = a.getAttribute('href') || '';
        if (!productHrefRe.test(href)) continue;
        const t = (a.innerText || a.textContent || '').trim();
        if (t && t.length >= 3 && t.length < 200) out.add(t);
      }

      // Product-shaped image alt text
      const productImgRe = /(product|catalog|catalogue|prod|item|service)/i;
      for (const img of document.querySelectorAll('img[alt]')) {
        const src = img.getAttribute('src') || img.getAttribute('data-src') || '';
        const alt = (img.getAttribute('alt') || '').trim();
        if (alt && alt.length >= 3 && alt.length < 200 && (productImgRe.test(src) || productImgRe.test(alt))) {
          out.add(alt);
        }
      }

      // Headings inside product cards
      const cardSel = '[class*="product"], [class*="catalog"], [class*="catalogue"], [class*="item-card"], [class*="prd"]';
      for (const c of document.querySelectorAll(cardSel)) {
        for (const h of c.querySelectorAll('h2, h3, h4, [class*="title"], [class*="name"]')) {
          const t = (h.innerText || h.textContent || '').trim();
          if (t && t.length >= 3 && t.length < 200) out.add(t);
        }
      }

      return Array.from(out).slice(0, 200);
    }
    """
    try:
        js_titles = page.evaluate(js) or []
        for t in js_titles:
            _add(t)
    except Exception:
        pass

    return titles[:max_titles]


def _pw_count_products(page, url: str, company: str) -> int:
    """Multi-strategy product counter.

    Order of strategies (most reliable first):
      1. JSON-LD schema (Product / ItemList / OfferCatalog) — explicit machine data
      2. Text patterns — "24 Products", "Showing 1-12 of 24", "View All (24)"
      3. JS heuristics — distinct product anchors / uniform grid kids / product images
      4. CSS selector median — fallback if everything else fails
    """
    if not _goto(page, url):
        return 0
    _wait(page, 2000)

    # Trigger lazy-loading
    _autoscroll(page)
    _wait(page, 500)

    # Strategy 1 — JSON-LD
    n = _count_jsonld_products(page)
    if n > 0:
        return n

    # Strategy 2 — text patterns
    text = _page_text(page)
    n = _extract_any_count(text, _PRODUCT_TEXT_KEYWORDS)
    if n > 0:
        return n

    # Strategy 3 — JS heuristics (DOM-driven)
    n = _count_via_js_heuristics(page)
    if n > 0:
        return n

    # Strategy 4 — CSS selector fallback
    return _count_via_css_selectors(page)


def _pw_justdial_products(page, profile_url: str, company: str) -> int:
    """Visit JustDial profile, navigate to catalogue tab, count products via DOM."""
    if not profile_url:
        return 0

    # JustDial-specific URL variants to try (catalogue tab + base profile)
    candidates = [
        profile_url.rstrip("/") + "/catalogue",
        profile_url.rstrip("/") + "/products",
        profile_url,
    ]

    for url in candidates:
        if not _goto(page, url):
            continue
        _wait(page, 2000)

        # If on base profile, try clicking through to catalogue tab
        if url == profile_url:
            for tab_sel in [
                "a[href*='catalogue']", "a[href*='catalog']",
                "a[href*='products']",
                "button:has-text('Products')", "a:has-text('Products')",
                "a:has-text('Catalogue')", "[class*='tab']:has-text('Product')",
            ]:
                try:
                    el = page.query_selector(tab_sel)
                    if el:
                        el.click()
                        _wait(page, 1500)
                        break
                except Exception:
                    pass

        # Trigger lazy-loaded catalog cards
        _autoscroll(page)
        _wait(page, 500)

        # Strategy 1 — JSON-LD (JustDial sometimes embeds OfferCatalog)
        n = _count_jsonld_products(page)
        if n > 0:
            return n

        # Strategy 2 — text patterns
        text = _page_text(page)
        n = _extract_any_count(text, [
            "Products", "Services", "Catalogue", "Items", "Catalog",
        ])
        if n > 0:
            return n

        # Strategy 3 — JustDial-specific DOM: catalogue cards have class
        # patterns like `jd-cat-list`, `jdcat`, `catbox`, plus generic ones
        jd_js = """
        () => {
          const sels = [
            '[class*="jdcat"]', '[class*="jd-cat"]', '[class*="jd-catalog"]',
            '[class*="catprod"]', '[class*="catbox"]',
            '[class*="catalogue-item"]', '[class*="catalog-item"]',
            '[class*="cat-item"]', '[class*="prdlist"] > li',
            '[class*="product-item"]', '[class*="service-item"]',
            'ul[class*="catalog"] > li', 'div[class*="catalog"] > div',
          ];
          let best = 0;
          for (const s of sels) {
            try {
              const items = document.querySelectorAll(s);
              if (items.length >= 1 && items.length < 500 && items.length > best) {
                best = items.length;
              }
            } catch (e) {}
          }
          return best;
        }
        """
        try:
            n = page.evaluate(jd_js)
            if n and int(n) > 0:
                return int(n)
        except Exception:
            pass

        # Strategy 4 — generic heuristics
        n = _count_via_js_heuristics(page)
        if n > 0:
            return n

    return 0


def _pw_tradeindia(page, hints: dict) -> dict:
    """Search TradeIndia for seller, return found status + product count."""
    empty = {"found": False, "product_count": 0, "rating": 0.0,
             "reviews": 0, "categories": [], "url": ""}
    company = hints["company_name"]
    city    = hints["city"]
    gst     = hints["gst"]

    search_terms = [f"{company} {city}".strip(), company]
    if gst:
        search_terms.insert(0, gst)

    for term in search_terms:
        try:
            search_url = f"https://www.tradeindia.com/search.html?search={quote(term)}"
            if not _goto(page, search_url):
                continue
            _wait(page, 2500)
            text = _page_text(page)
            if not text or len(text) < 200:
                continue

            result_selectors = [
                ".company-name a", ".comp-name a",
                "[class*='company-title'] a", "[class*='supplier'] a",
                "h3.comp-name a", "h2 a", "a[href*='/Seller/']",
            ]
            best_el, best_score = None, 0.0
            best_href = ""
            for sel in result_selectors:
                try:
                    for el in page.query_selector_all(sel)[:12]:
                        name = el.inner_text().strip()
                        href = el.get_attribute("href") or ""
                        score = _name_score(company, name)
                        if score > best_score:
                            best_score, best_el, best_href = score, el, href
                except Exception:
                    pass

            if best_el and best_score >= 0.4:
                try:
                    if best_href and best_href.startswith("http"):
                        _goto(page, best_href)
                    else:
                        best_el.click()
                    _wait(page, 2500)

                    profile_url = page.url
                    profile_text = _page_text(page)

                    product_count = _pw_count_products(page, profile_url, company)
                    try:
                        product_titles = _pw_extract_titles(page)
                    except Exception:
                        product_titles = []

                    categories = []
                    for sel in ["[class*='breadcrumb'] li", "h1", "[class*='category']"]:
                        try:
                            for el in page.query_selector_all(sel)[:3]:
                                t = el.inner_text().strip()
                                if t and len(t) < 80:
                                    categories.append(t)
                            if categories:
                                break
                        except Exception:
                            pass

                    return {
                        "found":          True,
                        "product_count":  product_count,
                        "product_titles": product_titles,
                        "rating":         0.0,
                        "reviews":        0,
                        "categories":     categories[:3],
                        "url":            profile_url,
                    }
                except Exception:
                    pass
        except Exception:
            continue

    # Fallback: direct slug URL check
    slug = _to_slug(company)
    for url in [
        f"https://www.tradeindia.com/Seller/{slug}/",
        f"https://www.tradeindia.com/seller/{slug.lower()}/",
    ]:
        try:
            if not _goto(page, url):
                continue
            _wait(page, 2000)
            text = _page_text(page)
            if text and _name_score(company, text) >= 0.4:
                product_count = _pw_count_products(page, url, company)
                try:
                    product_titles = _pw_extract_titles(page)
                except Exception:
                    product_titles = []
                return {
                    "found": True, "product_count": product_count,
                    "product_titles": product_titles,
                    "rating": 0.0, "reviews": 0, "categories": [], "url": page.url,
                }
        except Exception:
            pass

    return empty


def _pw_own_website(page, hints: dict) -> dict:
    """Check seller's own website from email domain, count products."""
    empty = {"found": False, "product_count": 0, "url": ""}
    domain = hints.get("email_domain", "")
    if not domain or domain in _GENERIC_DOMAINS:
        return empty

    base_url = f"https://{domain}"
    try:
        if not _goto(page, base_url):
            try:
                page.goto(f"http://{domain}", wait_until="domcontentloaded", timeout=_PW_TIMEOUT)
            except Exception:
                return empty

        _wait(page, 2000)
        text = _page_text(page)
        if not text or len(text) < 100:
            return empty

        final_url = page.url

        # Check if it's a real website (not a parked domain)
        parked_signals = ["domain for sale", "buy this domain", "parked domain",
                          "godaddy", "namecheap", "underconstruction"]
        if any(s in text.lower() for s in parked_signals):
            return empty

        product_count = _pw_count_products(page, final_url, hints["company_name"])

        # Try /products or /catalogue page if home shows 0
        if product_count == 0:
            for path in ["/products", "/catalogue", "/products.html",
                         "/our-products", "/product-range"]:
                try:
                    prod_url = final_url.rstrip("/") + path
                    page.goto(prod_url, wait_until="domcontentloaded", timeout=8000)
                    _wait(page, 1500)
                    n = _pw_count_products(page, prod_url, hints["company_name"])
                    if n > 0:
                        product_count = n
                        break
                except Exception:
                    pass

        try:
            product_titles = _pw_extract_titles(page)
        except Exception:
            product_titles = []

        return {
            "found":          True,
            "product_count":  product_count,
            "product_titles": product_titles,
            "url":            final_url,
            "domain":         domain,
        }
    except Exception:
        return empty


# ── Gap + call card ──────────────────────────────────────────────────────────

def _compute_gap(im_count: int, platform_data: dict) -> dict:
    """Combine competitor product counts across platforms.

    Preferred path — NAME-BASED DEDUPE (robust):
      If any platform has scraped product titles, cluster matching titles
      across platforms (Jaccard token overlap + substring containment).
      The true competitor catalogue size = number of distinct clusters.

    Fallback path — COUNT-BASED HEURISTIC (when titles missing):
      - All counts within 30% of max → likely overlapping catalogues → MAX
      - Counts differ widely → likely distinct catalogues → SUM
      - One platform only → use directly
    """
    other_counts = [
        d.get("product_count", 0)
        for d in platform_data.values()
        if d.get("found") and d.get("product_count", 0) > 0
    ]
    titles_by_platform = {
        p: (d.get("product_titles") or [])
        for p, d in platform_data.items()
        if d.get("found")
    }
    has_titles = sum(len(v) for v in titles_by_platform.values()) >= 3

    if not other_counts and not has_titles:
        return {"im_products": im_count, "other_total_products": 0,
                "other_max_products": 0, "other_combination": "none",
                "gap_pct": 0, "severity": "unknown",
                "match_method": "none",
                "overlap_pairs": [], "per_platform_unique": {}}

    # ---- Path A: name-based dedupe ----
    if has_titles:
        dd = _dedupe_across_platforms(titles_by_platform)
        unique_via_names = dd["unique_count"]

        # If unique_via_names is suspiciously lower than the reported count for any
        # platform (e.g. JustDial reports 24 products but we only scraped 8 titles),
        # don't penalize — fall back to the max of (name-unique, max raw count).
        max_raw_count = max(other_counts) if other_counts else 0
        other_total = max(unique_via_names, max_raw_count)

        # Combination label inferred from cluster structure
        if not other_counts:
            combination = "name_dedupe"
        elif unique_via_names < sum(other_counts) * 0.65:
            combination = "name_dedupe_overlap"   # heavy cross-listing
        else:
            combination = "name_dedupe_distinct"  # mostly unique per platform

        gap_pct = round((im_count - other_total) / max(other_total, 1) * 100, 1)
        sev = "high" if gap_pct < -40 else "medium" if gap_pct < -20 else "low"

        return {
            "im_products":          im_count,
            "other_total_products": other_total,
            "other_max_products":   max_raw_count,
            "other_combination":    combination,
            "platform_counts":      other_counts,
            "other_avg_products":   other_total,  # back-compat
            "gap_pct":              gap_pct,
            "severity":             sev,
            "match_method":         "names",
            "unique_via_names":     unique_via_names,
            "overlap_pairs":        [{"platforms": [p1, p2], "shared": c}
                                     for p1, p2, c in dd["overlap_pairs"]],
            "per_platform_unique":  dd["per_platform_unique"],
            "titles_sampled":       {p: t[:20] for p, t in titles_by_platform.items() if t},
        }

    # ---- Path B: count-based heuristic ----
    max_cnt = max(other_counts)
    sum_cnt = sum(other_counts)

    if len(other_counts) == 1:
        other_total = max_cnt
        combination = "single"
    else:
        threshold = max_cnt * 0.7
        if all(c >= threshold for c in other_counts):
            other_total = max_cnt
            combination = "max_overlap"
        else:
            other_total = sum_cnt
            combination = "sum_distinct"

    gap_pct = round((im_count - other_total) / max(other_total, 1) * 100, 1)
    sev = "high" if gap_pct < -40 else "medium" if gap_pct < -20 else "low"

    return {
        "im_products":          im_count,
        "other_total_products": other_total,
        "other_max_products":   max_cnt,
        "other_combination":    combination,
        "platform_counts":      other_counts,
        "other_avg_products":   other_total,
        "gap_pct":              gap_pct,
        "severity":             sev,
        "match_method":         "counts",
        "overlap_pairs":        [],
        "per_platform_unique":  {},
    }


def _build_call_card(company: str, gap: dict, platform_data: dict, hints: dict) -> dict:
    first = company.split()[0] if company else "Bhai"
    data_points = []

    for platform, d in platform_data.items():
        if not d.get("found"):
            continue
        label = "Own Website" if platform == "own_website" else platform.title()
        parts = [f"{label}: Listed"]
        if d.get("product_count", 0) > 0:
            parts.append(f"{d['product_count']} products")
        elif d.get("photo_count", 0) > 0:
            parts.append(f"{d['photo_count']} photos")
        if d.get("rating", 0) > 0:
            parts.append(f"Rating {d['rating']}/5")
        if d.get("reviews", 0) > 0:
            parts.append(f"{d['reviews']} reviews")
        data_points.append(" | ".join(parts))

    if hints.get("gst"):
        data_points.append(f"GST: {hints['gst']}")
    if hints.get("address"):
        data_points.append(f"Address: {hints['address'][:80]}")

    found_any = any(d.get("found") for d in platform_data.values())
    if not found_any:
        return {
            "headline_hi": "Aapka account kisi aur platform pe nahi mila — IM pe hi strongest presence hai.",
            "headline_en": "Seller not found on other platforms — IndiaMART is their primary channel.",
            "data_points": data_points,
            "suggested_action": "Strengthen IM catalog — unmatched B2B buyer volume.",
            "urgency": "low",
        }

    found_platform = next((p for p, d in platform_data.items() if d.get("found")), "")
    label = "Own Website" if found_platform == "own_website" else found_platform.title()
    other_count = int(gap.get("other_avg_products", 0))
    sev = gap.get("severity", "unknown")

    if sev in ("high", "medium"):
        headline_hi = (
            f"{first} Bhai, aapka {label} pe {other_count} products hain "
            f"— IM pe sirf {gap['im_products']} hain. IM pe B2B buyers 3× zyada hain."
        )
        headline_en = (
            f"Your {label} listing has {other_count} products. "
            f"IndiaMART shows only {gap['im_products']}. IM has 3× more B2B buyers."
        )
        suggested_action = f"Mirror {label} catalog on IndiaMART — 20 min upload"
        urgency = sev
    else:
        headline_hi = f"{first} Bhai, aap {label} pe bhi listed hain — IM catalog fresh rakho."
        headline_en = f"Listed on {label} too. IndiaMART catalog at parity — keep it updated."
        suggested_action = "Maintain catalog sync quarterly."
        urgency = "low"

    return {
        "headline_hi": headline_hi,
        "headline_en": headline_en,
        "data_points": data_points[:6],
        "suggested_action": suggested_action,
        "effort_estimate": "20 minutes",
        "urgency": urgency,
    }


def _positioning(gap: dict) -> str:
    gp = gap.get("gap_pct", 0)
    if gp < -20:
        return "seller_stronger_elsewhere"
    if gp > 20:
        return "seller_stronger_on_im"
    return "parity"


# ── Skill ────────────────────────────────────────────────────────────────────

class CrossPlatformIntelligenceSkill(Skill):
    name = "cross_platform_intelligence"
    required_inputs = ["glid", "company", "city"]
    optional_inputs = ["mcats", "rca_category", "ctype", "im_product_count"]

    def invoke(self, inputs: dict) -> SkillResult:
        company  = inputs["company"].strip()
        city     = inputs.get("city", "").strip()
        glid     = inputs["glid"]
        im_count = inputs.get("im_product_count", 0) or 0

        if not company:
            return SkillResult(success=False,
                               data={"skipped": True, "reason": "no company name"},
                               used_fallback=True)

        ctx   = _fetch_context(glid)
        hints = _extract_hints(ctx, company, city)
        if hints["approved_products"] > 0 and im_count == 0:
            im_count = hints["approved_products"]

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return SkillResult(success=False,
                               data={"skipped": True, "reason": "playwright not installed"},
                               used_fallback=True)

        sess         = _session()
        platform_data: dict = {}

        # Phase 1: requests — fast JustDial discovery
        jd_base = _jd_discover(hints, sess)
        platform_data["justdial"] = jd_base

        # Phase 2: Playwright — product counts
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage",
                          "--disable-blink-features=AutomationControlled",
                          "--disable-web-security", "--lang=en-IN"],
                )
                ctx_browser = browser.new_context(
                    user_agent=_USER_AGENT,
                    viewport={"width": 1366, "height": 768},
                    locale="en-IN",
                    timezone_id="Asia/Kolkata",
                )
                ctx_browser.add_init_script(
                    "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
                    "Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3]});"
                )
                page = ctx_browser.new_page()
                page.set_default_timeout(_PW_TIMEOUT)

                # JustDial: get product count from profile page.
                # Only overwrite if Playwright found MORE than the discovery
                # phase did (some sellers have catalog photos that aren't in
                # the search listing's `dimages`).
                if jd_base.get("found") and jd_base.get("url"):
                    jd_products = _pw_justdial_products(page, jd_base["url"], hints["company_name"])
                    existing = platform_data["justdial"].get("product_count", 0) or 0
                    if jd_products > existing:
                        platform_data["justdial"]["product_count"] = jd_products
                    # Capture titles from the current page (catalogue tab) for name-matching
                    try:
                        jd_titles = _pw_extract_titles(page)
                        if jd_titles:
                            platform_data["justdial"]["product_titles"] = jd_titles
                    except Exception:
                        pass

                # TradeIndia: full search + product count + titles
                _wait(page, 1000)
                platform_data["tradeindia"] = _pw_tradeindia(page, hints)

                # Own website: email domain check
                _wait(page, 1000)
                if hints.get("email_domain") and hints["email_domain"] not in _GENERIC_DOMAINS:
                    platform_data["own_website"] = _pw_own_website(page, hints)

                browser.close()

        except Exception as e:
            platform_data.setdefault("tradeindia", {"found": False, "product_count": 0,
                                                    "url": "", "error": str(e)})

        platforms_found = [p for p, d in platform_data.items() if d.get("found")]
        gap  = _compute_gap(im_count, platform_data)
        card = _build_call_card(hints["company_name"], gap, platform_data, hints)

        return SkillResult(
            success=True,
            data={
                "platforms_found":         platforms_found,
                "platform_data":           platform_data,
                "im_catalog_gap":          gap,
                "call_card":               card,
                "competitive_positioning": _positioning(gap),
                "scrape_status":           "success",
                "context_enriched":        bool(ctx),
                "company_name_used":       hints["company_name"],
                "im_product_count":        im_count,
                "gst":                     hints["gst"],
                "address":                 hints["address"],
                "own_website_domain":      hints.get("email_domain", ""),
            },
        )

    def fallback(self, inputs: dict, error: Exception) -> SkillResult:
        return SkillResult(
            success=False, used_fallback=True,
            data={"platforms_found": [], "platform_data": {}, "im_catalog_gap": {},
                  "call_card": {}, "scrape_status": "failed", "error": str(error)},
        )
