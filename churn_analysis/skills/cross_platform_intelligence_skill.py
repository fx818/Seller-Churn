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
    m = re.search(rf"(\d[\d,]*)\s*{re.escape(keyword)}", text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return 0


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
            product_count = ev_svc or sc_count or price_count
            photocnt = int(_get(best_row, "photocnt") or 0)
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

def _pw_count_products(page, url: str, company: str) -> int:
    """Visit a page and count products using multiple selector strategies."""
    if not _goto(page, url):
        return 0
    _wait(page, 2000)
    text = _page_text(page)

    # Try structured count from text first
    for kw in ["Products", "Services", "Items", "products", "services"]:
        n = _extract_number(text, kw)
        if n > 0:
            return n

    # Count product card elements
    product_selectors = [
        "[class*='product-item']", "[class*='product-card']",
        "[class*='ProductCard']", "[class*='product_item']",
        "[class*='catalogue-item']", "[class*='catalog-item']",
        ".product", ".prod-item", ".item-card",
        "[class*='listing-item']", "[class*='product-list'] li",
        ".grid-item", "[class*='prd-box']",
    ]
    for sel in product_selectors:
        try:
            items = page.query_selector_all(sel)
            if len(items) >= 2:
                return len(items)
        except Exception:
            pass

    return 0


def _pw_justdial_products(page, profile_url: str, company: str) -> int:
    """Visit JustDial profile catalog tab and count products."""
    if not profile_url:
        return 0
    try:
        catalogue_url = profile_url.rstrip("/") + "/catalogue"
        for url in [catalogue_url, profile_url]:
            if not _goto(page, url):
                continue
            _wait(page, 2500)

            if url == profile_url:
                for tab_sel in [
                    "a[href*='catalogue']", "a[href*='catalog']",
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

            text = _page_text(page)
            for kw in ["Products", "Services", "Catalogue", "Items"]:
                n = _extract_number(text, kw)
                if n > 0:
                    return n

            for sel in [
                "[class*='catalogue']", "[class*='catalog-item']",
                "[class*='catprod']", "[class*='jd-catalog']",
                "[class*='product-item']", ".jdcatalog li",
                "[class*='service-list'] li", "[class*='serv-list'] li",
                ".cat-item", "[class*='prodlist'] li",
            ]:
                try:
                    items = page.query_selector_all(sel)
                    if len(items) >= 1:
                        return len(items)
                except Exception:
                    pass

    except Exception:
        pass
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
                        "found":         True,
                        "product_count": product_count,
                        "rating":        0.0,
                        "reviews":       0,
                        "categories":    categories[:3],
                        "url":           profile_url,
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
                return {
                    "found": True, "product_count": product_count,
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

        return {
            "found":         True,
            "product_count": product_count,
            "url":           final_url,
            "domain":        domain,
        }
    except Exception:
        return empty


# ── Gap + call card ──────────────────────────────────────────────────────────

def _compute_gap(im_count: int, platform_data: dict) -> dict:
    other_counts = [
        d["product_count"]
        for d in platform_data.values()
        if d.get("found") and d.get("product_count", 0) > 0
    ]
    if not other_counts:
        return {"im_products": im_count, "other_avg_products": 0,
                "gap_pct": 0, "severity": "unknown"}
    avg     = sum(other_counts) / len(other_counts)
    gap_pct = round((im_count - avg) / max(avg, 1) * 100, 1)
    sev     = "high" if gap_pct < -40 else "medium" if gap_pct < -20 else "low"
    return {"im_products": im_count, "other_avg_products": round(avg, 1),
            "gap_pct": gap_pct, "severity": sev}


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

                # JustDial: get product count from profile page
                if jd_base.get("found") and jd_base.get("url"):
                    jd_products = _pw_justdial_products(page, jd_base["url"], hints["company_name"])
                    platform_data["justdial"]["product_count"] = jd_products

                # TradeIndia: full search + product count
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
