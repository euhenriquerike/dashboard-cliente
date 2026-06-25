#!/usr/bin/env python3
import json
import os
import requests
from datetime import datetime, timedelta



_meta_currency_cache = None


# ── Meta Ads (demo data) ──────────────────────────────────────────────────────

def _meta_base(n):
    spend = round(280.0 * n, 2)
    imp = 42000 * n
    clicks = 840 * n
    purchases = int(24 * n)
    rev = round(5040.0 * n, 2)
    return {
        "spend": spend, "impressions": imp, "clicks": clicks, "reach": int(32000 * n),
        "cpm": round(spend / imp * 1000, 6) if imp else 0,
        "cpc": round(spend / clicks, 6) if clicks else 0,
        "ctr": round(clicks / imp * 100, 6) if imp else 0,
        "purchases": purchases, "revenue": rev,
        "cpa": round(spend / purchases, 2) if purchases else 0,
        "roas": round(rev / spend, 4) if spend else 0,
        "currency": "USD",
    }


def fetch_meta(since, until):
    from datetime import date as _date
    n = (_date.fromisoformat(until) - _date.fromisoformat(since)).days + 1
    return _meta_base(n)


def fetch_meta_breakdown(since, until, level):
    from datetime import date as _date
    n = (_date.fromisoformat(until) - _date.fromisoformat(since)).days + 1
    camps = [
        {"name": "ASC_ALL — DPA Catalog — SALES", "w": 0.60},
        {"name": "RETARGETING — Site Visitors 30d", "w": 0.30},
        {"name": "PROSPECTING — Lookalike 1-3%", "w": 0.10},
    ]
    adsets = [
        {"name": "Advantage+ Placement — DPA Catalog", "camp": "ASC_ALL — DPA Catalog — SALES", "w": 0.60},
        {"name": "Retargeting — Website Visitors 30d", "camp": "RETARGETING — Site Visitors 30d", "w": 0.30},
        {"name": "Lookalike 1-3% — All Purchasers", "camp": "PROSPECTING — Lookalike 1-3%", "w": 0.10},
    ]
    ads_list = [
        {"name": "DPA_Carousel_MultiProduct_v1", "adset": "Advantage+ Placement — DPA Catalog", "camp": "ASC_ALL — DPA Catalog — SALES", "w": 0.36},
        {"name": "DPA_SingleImage_ProductFeed_v2", "adset": "Advantage+ Placement — DPA Catalog", "camp": "ASC_ALL — DPA Catalog — SALES", "w": 0.24},
        {"name": "Video_Retargeting_30s_Offer", "adset": "Retargeting — Website Visitors 30d", "camp": "RETARGETING — Site Visitors 30d", "w": 0.30},
        {"name": "Static_Lookalike_BrandOffer", "adset": "Lookalike 1-3% — All Purchasers", "camp": "PROSPECTING — Lookalike 1-3%", "w": 0.10},
    ]
    base = _meta_base(n)
    items = {"campaign": camps, "adset": adsets, "ad": ads_list}[level]
    rows = []
    for item in items:
        w = item["w"]
        spend = round(base["spend"] * w, 2)
        imp = int(base["impressions"] * w)
        clicks = int(base["clicks"] * w)
        purchases = int(base["purchases"] * w)
        rev = round(base["revenue"] * w, 2)
        row = {
            "name": item["name"], "spend": spend, "impressions": imp, "clicks": clicks,
            "reach": int(base["reach"] * w),
            "cpm": round(spend / imp * 1000, 6) if imp else 0,
            "cpc": round(spend / clicks, 6) if clicks else 0,
            "ctr": round(clicks / imp * 100, 6) if imp else 0,
            "purchases": purchases, "revenue": rev,
            "cpa": round(spend / purchases, 2) if purchases else 0,
            "roas": round(rev / spend, 4) if spend else 0,
        }
        if level in ("adset", "ad"):
            row["campaign"] = item["camp"]
        if level == "ad":
            row["adset"] = item["adset"]
        rows.append(row)
    return rows


def fetch_meta_geo(since, until):
    from datetime import date as _date
    n = (_date.fromisoformat(until) - _date.fromisoformat(since)).days + 1
    base = _meta_base(n)
    geos = [("United States", 0.68), ("United Kingdom", 0.17), ("Canada", 0.15)]
    rows = []
    for country, w in geos:
        spend = round(base["spend"] * w, 2)
        imp = int(base["impressions"] * w)
        clicks = int(base["clicks"] * w)
        purchases = int(base["purchases"] * w)
        rows.append({
            "country": country, "spend": spend, "impressions": imp, "clicks": clicks,
            "cpm": round(spend / imp * 1000, 6) if imp else 0,
            "cpc": round(spend / clicks, 6) if clicks else 0,
            "ctr": round(clicks / imp * 100, 6) if imp else 0,
            "purchases": purchases,
        })
    return rows


# ── Google Ads (demo data) ────────────────────────────────────────────────────

def _gads_base(n):
    spend = round(195.0 * n, 2)
    imp = 38500 * n
    clicks = 1733 * n
    conv = int(38 * n)
    rev = round(5890.0 * n, 2)
    return {
        "spend": spend, "impressions": imp, "clicks": clicks,
        "cpm": round(spend / imp * 1000, 6) if imp else 0,
        "cpc": round(spend / clicks, 6) if clicks else 0,
        "ctr": round(clicks / imp * 100, 6) if imp else 0,
        "conversions": conv, "revenue": rev,
        "cpa": round(spend / conv, 2) if conv else 0,
        "roas": round(rev / spend, 4) if spend else 0,
        "currency": "USD",
    }


def fetch_google_ads(since, until):
    from datetime import date as _date
    n = (_date.fromisoformat(until) - _date.fromisoformat(since)).days + 1
    return _gads_base(n)


def fetch_google_campaigns(since, until):
    from datetime import date as _date
    n = (_date.fromisoformat(until) - _date.fromisoformat(since)).days + 1
    base = _gads_base(n)
    items = [
        {"name": "PMax — All Products", "status": "ENABLED", "w": 0.50},
        {"name": "Search — Brand Keywords", "status": "ENABLED", "w": 0.30},
        {"name": "Search — Category Keywords", "status": "ENABLED", "w": 0.20},
    ]
    rows = []
    for item in items:
        w = item["w"]
        spend = round(base["spend"] * w, 2)
        imp = int(base["impressions"] * w)
        clicks = int(base["clicks"] * w)
        conv = int(base["conversions"] * w)
        rev = round(base["revenue"] * w, 2)
        rows.append({
            "name": item["name"], "status": item["status"], "spend": spend,
            "impressions": imp, "clicks": clicks,
            "cpm": round(spend / imp * 1000, 6) if imp else 0,
            "cpc": round(spend / clicks, 6) if clicks else 0,
            "ctr": round(clicks / imp * 100, 6) if imp else 0,
            "conversions": conv, "revenue": rev,
            "cpa": round(spend / conv, 2) if conv else 0,
            "roas": round(rev / spend, 4) if spend else 0,
        })
    return rows


def fetch_google_adgroups(since, until):
    from datetime import date as _date
    n = (_date.fromisoformat(until) - _date.fromisoformat(since)).days + 1
    base = _gads_base(n)
    items = [
        {"name": "All Products — Shopping", "camp": "PMax — All Products", "w": 0.28},
        {"name": "Performance Max — Dynamic", "camp": "PMax — All Products", "w": 0.22},
        {"name": "Brand — Exact Match", "camp": "Search — Brand Keywords", "w": 0.30},
        {"name": "Category — Broad Match", "camp": "Search — Category Keywords", "w": 0.20},
    ]
    rows = []
    for item in items:
        w = item["w"]
        spend = round(base["spend"] * w, 2)
        imp = int(base["impressions"] * w)
        clicks = int(base["clicks"] * w)
        conv = int(base["conversions"] * w)
        rev = round(base["revenue"] * w, 2)
        rows.append({
            "name": item["name"], "campaign": item["camp"], "status": "ENABLED",
            "spend": spend, "impressions": imp, "clicks": clicks,
            "cpm": round(spend / imp * 1000, 6) if imp else 0,
            "cpc": round(spend / clicks, 6) if clicks else 0,
            "ctr": round(clicks / imp * 100, 6) if imp else 0,
            "conversions": conv, "revenue": rev,
            "cpa": round(spend / conv, 2) if conv else 0,
            "roas": round(rev / spend, 4) if spend else 0,
        })
    return rows


def fetch_google_ads_breakdown(since, until):
    from datetime import date as _date
    n = (_date.fromisoformat(until) - _date.fromisoformat(since)).days + 1
    base = _gads_base(n)
    items = [
        {"name": "RSA — Brand Core", "adset": "Brand — Exact Match", "camp": "Search — Brand Keywords", "w": 0.30},
        {"name": "RSA — Category Main", "adset": "Category — Broad Match", "camp": "Search — Category Keywords", "w": 0.20},
        {"name": "Responsive Display — Product A", "adset": "All Products — Shopping", "camp": "PMax — All Products", "w": 0.28},
        {"name": "Smart Display — Retargeting", "adset": "Performance Max — Dynamic", "camp": "PMax — All Products", "w": 0.22},
    ]
    rows = []
    for item in items:
        w = item["w"]
        spend = round(base["spend"] * w, 2)
        imp = int(base["impressions"] * w)
        clicks = int(base["clicks"] * w)
        conv = int(base["conversions"] * w)
        rev = round(base["revenue"] * w, 2)
        rows.append({
            "name": item["name"], "campaign": item["camp"], "adset": item["adset"],
            "status": "ENABLED", "spend": spend, "impressions": imp, "clicks": clicks,
            "cpm": round(spend / imp * 1000, 6) if imp else 0,
            "cpc": round(spend / clicks, 6) if clicks else 0,
            "ctr": round(clicks / imp * 100, 6) if imp else 0,
            "conversions": conv, "revenue": rev,
            "cpa": round(spend / conv, 2) if conv else 0,
            "roas": round(rev / spend, 4) if spend else 0,
        })
    return rows


def fetch_google_geo(since, until):
    from datetime import date as _date
    n = (_date.fromisoformat(until) - _date.fromisoformat(since)).days + 1
    base = _gads_base(n)
    geos = [("United States", 0.75), ("Canada", 0.16), ("United Kingdom", 0.09)]
    rows = []
    for country, w in geos:
        spend = round(base["spend"] * w, 2)
        imp = int(base["impressions"] * w)
        clicks = int(base["clicks"] * w)
        conv = int(base["conversions"] * w)
        rev = round(base["revenue"] * w, 2)
        rows.append({
            "country": country, "spend": spend, "impressions": imp, "clicks": clicks,
            "cpm": round(spend / imp * 1000, 6) if imp else 0,
            "cpc": round(spend / clicks, 6) if clicks else 0,
            "ctr": round(clicks / imp * 100, 6) if imp else 0,
            "conversions": conv,
        })
    return rows


# ── GA4 ────────────────────────────────────────────────────────────────────────

def _ga4_via_rest(since, until, access_token):
    prop = os.environ["GA4_PROPERTY_ID"].strip()
    r = requests.post(
        f"https://analyticsdata.googleapis.com/v1beta/properties/{prop}:runReport",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "dateRanges": [{"startDate": since, "endDate": until}],
            "metrics": [
                {"name": "sessions"}, {"name": "totalUsers"}, {"name": "transactions"},
                {"name": "purchaseRevenue"}, {"name": "sessionConversionRate"},
            ],
        },
        timeout=30,
    )
    data = r.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("message", str(data["error"])))
    rows = data.get("rows", [])
    if not rows:
        return {"sessions": 0, "users": 0, "transactions": 0, "revenue": 0.0, "conversion_rate": 0.0}
    v = [mv["value"] for mv in rows[0]["metricValues"]]
    return {"sessions": int(v[0]), "users": int(v[1]), "transactions": int(v[2]), "revenue": float(v[3]), "conversion_rate": float(v[4]) * 100}


def fetch_ga4(since, until):
    from datetime import date as _date
    n = (_date.fromisoformat(until) - _date.fromisoformat(since)).days + 1
    sessions = 3840 * n
    users = int(sessions * 0.789)
    transactions = int(sessions * 0.0229)
    revenue = round(transactions * 220.0, 2)
    return {"sessions": sessions, "users": users, "transactions": transactions, "revenue": revenue, "conversion_rate": 2.29}


# ── WooCommerce ─────────────────────────────────────────────────────────────────

def fetch_woocommerce(since, until):
    from datetime import date as _date
    n = (_date.fromisoformat(until) - _date.fromisoformat(since)).days + 1
    orders = int(85 * n)
    revenue = round(18700.0 * n, 2)
    return {"orders": orders, "revenue": revenue, "avg_ticket": round(revenue / orders, 2), "currency": "USD"}



# ── TikTok Ads (demo data) ─────────────────────────────────────────────────────

def _tiktok_base(n):
    spend = round(155.0 * n, 2)
    imp = 87400 * n
    clicks = 1311 * n
    conv = int(12 * n)
    rev = round(3085.0 * n, 2)
    return {
        "spend": spend, "impressions": imp, "clicks": clicks,
        "reach": int(65000 * n),
        "cpm": round(spend / imp * 1000, 6) if imp else 0,
        "cpc": round(spend / clicks, 6) if clicks else 0,
        "ctr": round(clicks / imp * 100, 6) if imp else 0,
        "conversions": conv, "revenue": rev,
        "cpa": round(spend / conv, 2) if conv else 0,
        "roas": round(rev / spend, 4) if spend else 0,
        "currency": "USD",
    }


def fetch_tiktok(since, until):
    from datetime import date as _date
    n = (_date.fromisoformat(until) - _date.fromisoformat(since)).days + 1
    return _tiktok_base(n)


def fetch_tiktok_breakdown(since, until, level):
    from datetime import date as _date
    n = (_date.fromisoformat(until) - _date.fromisoformat(since)).days + 1
    camps = [
        {"name": "TK_SALES_CATALOG", "w": 0.57},
        {"name": "TK_RETARGETING_WEBSITE", "w": 0.27},
        {"name": "TK_AWARENESS_BROAD", "w": 0.16},
    ]
    adsets = [
        {"name": "Lookalike 1-3% — Purchasers", "camp": "TK_SALES_CATALOG", "w": 0.35},
        {"name": "Broad — Video Views", "camp": "TK_SALES_CATALOG", "w": 0.22},
        {"name": "Retargeting — Website Visitors 30d", "camp": "TK_RETARGETING_WEBSITE", "w": 0.27},
        {"name": "Awareness — Interest Based", "camp": "TK_AWARENESS_BROAD", "w": 0.16},
    ]
    ads_list = [
        {"name": "Video_Catalog_Lifestyle_01", "adset": "Lookalike 1-3% — Purchasers", "camp": "TK_SALES_CATALOG", "w": 0.22},
        {"name": "Video_Catalog_Lifestyle_02", "adset": "Lookalike 1-3% — Purchasers", "camp": "TK_SALES_CATALOG", "w": 0.13},
        {"name": "Video_UGC_Testimonial_01", "adset": "Broad — Video Views", "camp": "TK_SALES_CATALOG", "w": 0.22},
        {"name": "Video_Retargeting_Promo", "adset": "Retargeting — Website Visitors 30d", "camp": "TK_RETARGETING_WEBSITE", "w": 0.27},
        {"name": "Video_Awareness_Brand", "adset": "Awareness — Interest Based", "camp": "TK_AWARENESS_BROAD", "w": 0.16},
    ]
    base = _tiktok_base(n)
    items = {"campaign": camps, "adset": adsets, "ad": ads_list}[level]
    rows = []
    for item in items:
        w = item["w"]
        spend = round(base["spend"] * w, 2)
        imp = int(base["impressions"] * w)
        clicks = int(base["clicks"] * w)
        conv = int(base["conversions"] * w)
        rev = round(base["revenue"] * w, 2)
        row = {
            "name": item["name"], "spend": spend, "impressions": imp, "clicks": clicks,
            "cpm": round(spend / imp * 1000, 6) if imp else 0,
            "cpc": round(spend / clicks, 6) if clicks else 0,
            "ctr": round(clicks / imp * 100, 6) if imp else 0,
            "conversions": conv, "revenue": rev,
            "cpa": round(spend / conv, 2) if conv else 0,
            "roas": round(rev / spend, 4) if spend else 0,
        }
        if level in ("adset", "ad"):
            row["campaign"] = item["camp"]
        if level == "ad":
            row["adset"] = item["adset"]
        rows.append(row)
    return rows


def fetch_tiktok_geo(since, until):
    from datetime import date as _date
    n = (_date.fromisoformat(until) - _date.fromisoformat(since)).days + 1
    base = _tiktok_base(n)
    geos = [("Brazil", 0.73), ("Portugal", 0.16), ("United States", 0.11)]
    rows = []
    for country, w in geos:
        spend = round(base["spend"] * w, 2)
        imp = int(base["impressions"] * w)
        clicks = int(base["clicks"] * w)
        conv = int(base["conversions"] * w)
        row = {
            "country": country, "spend": spend, "impressions": imp, "clicks": clicks,
            "cpm": round(spend / imp * 1000, 6) if imp else 0,
            "cpc": round(spend / clicks, 6) if clicks else 0,
            "ctr": round(clicks / imp * 100, 6) if imp else 0,
            "conversions": conv,
        }
        rows.append(row)
    return rows


# ── LinkedIn Ads (demo data) ───────────────────────────────────────────────────

def _linkedin_base(n):
    spend = round(85.0 * n, 2)
    imp = 4200 * n
    clicks = 126 * n
    conv = int(8 * n)
    rev = round(2320.0 * n, 2)
    return {
        "spend": spend, "impressions": imp, "clicks": clicks,
        "cpm": round(spend / imp * 1000, 6) if imp else 0,
        "cpc": round(spend / clicks, 6) if clicks else 0,
        "ctr": round(clicks / imp * 100, 6) if imp else 0,
        "conversions": conv, "revenue": rev,
        "cpa": round(spend / conv, 2) if conv else 0,
        "roas": round(rev / spend, 4) if spend else 0,
        "currency": "USD",
    }


def fetch_linkedin(since, until):
    from datetime import date as _date
    n = (_date.fromisoformat(until) - _date.fromisoformat(since)).days + 1
    return _linkedin_base(n)


def fetch_linkedin_breakdown(since, until, level):
    from datetime import date as _date
    n = (_date.fromisoformat(until) - _date.fromisoformat(since)).days + 1
    camps = [
        {"name": "LK_CONVERSIONS_RETARGETING", "w": 0.59},
        {"name": "LK_LEAD_GEN_COLD", "w": 0.41},
    ]
    adsets = [
        {"name": "Retargeting — Website 30d", "camp": "LK_CONVERSIONS_RETARGETING", "w": 0.59},
        {"name": "Cold — Job Function Targeting", "camp": "LK_LEAD_GEN_COLD", "w": 0.41},
    ]
    ads_list = [
        {"name": "Single Image — Promo Offer", "adset": "Retargeting — Website 30d", "camp": "LK_CONVERSIONS_RETARGETING", "w": 0.59},
        {"name": "Single Image — Brand Story", "adset": "Cold — Job Function Targeting", "camp": "LK_LEAD_GEN_COLD", "w": 0.41},
    ]
    base = _linkedin_base(n)
    items = {"campaign": camps, "adset": adsets, "ad": ads_list}[level]
    rows = []
    for item in items:
        w = item["w"]
        spend = round(base["spend"] * w, 2)
        imp = int(base["impressions"] * w)
        clicks = int(base["clicks"] * w)
        conv = int(base["conversions"] * w)
        rev = round(base["revenue"] * w, 2)
        row = {
            "name": item["name"], "spend": spend, "impressions": imp, "clicks": clicks,
            "cpm": round(spend / imp * 1000, 6) if imp else 0,
            "cpc": round(spend / clicks, 6) if clicks else 0,
            "ctr": round(clicks / imp * 100, 6) if imp else 0,
            "conversions": conv, "revenue": rev,
            "cpa": round(spend / conv, 2) if conv else 0,
            "roas": round(rev / spend, 4) if spend else 0,
        }
        if level in ("adset", "ad"):
            row["campaign"] = item["camp"]
        if level == "ad":
            row["adset"] = item["adset"]
        rows.append(row)
    return rows


def fetch_linkedin_geo(since, until):
    from datetime import date as _date
    n = (_date.fromisoformat(until) - _date.fromisoformat(since)).days + 1
    base = _linkedin_base(n)
    geos = [("Brazil", 0.65), ("Portugal", 0.24), ("United States", 0.11)]
    rows = []
    for country, w in geos:
        spend = round(base["spend"] * w, 2)
        imp = int(base["impressions"] * w)
        clicks = int(base["clicks"] * w)
        conv = int(base["conversions"] * w)
        row = {
            "country": country, "spend": spend, "impressions": imp, "clicks": clicks,
            "cpm": round(spend / imp * 1000, 6) if imp else 0,
            "cpc": round(spend / clicks, 6) if clicks else 0,
            "ctr": round(clicks / imp * 100, 6) if imp else 0,
            "conversions": conv,
        }
        rows.append(row)
    return rows

# ── HTML template ──────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__CLIENT_NAME__ — Dashboard</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f5f7;color:#1d1d1f}
header{background:#111;color:#fff;padding:20px 32px;display:flex;justify-content:space-between;align-items:center}
header h1{font-size:18px;font-weight:600;letter-spacing:-.01em}
.upd{font-size:12px;color:#777}
main{max-width:1280px;margin:0 auto;padding:28px 32px}
.tabs{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}
.tab{padding:8px 18px;border-radius:20px;font-size:13px;cursor:pointer;border:none;background:#e5e5ea;color:#1d1d1f;font-weight:500;transition:background .15s,color .15s}
.tab.active{background:#111;color:#fff}
.vtabs{margin-bottom:24px}
.vtabs .tab{font-size:12px;padding:6px 14px;background:#f2f2f7}
.vtabs .tab.active{background:#555;color:#fff}
.sec{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#86868b;margin:28px 0 14px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin-bottom:8px}
.card{background:#fff;border-radius:12px;padding:18px 20px}
.card.blue{background:#0055ff;color:#fff}
.lbl{font-size:11px;color:#86868b;margin-bottom:8px}
.card.blue .lbl{color:rgba(255,255,255,.65)}
.val{font-size:22px;font-weight:700;letter-spacing:-.02em;line-height:1}
.sub{font-size:11px;color:#86868b;margin-top:5px}
.card.blue .sub{color:rgba(255,255,255,.6)}
.tscroll{overflow-x:auto;margin-bottom:8px}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden}
th{text-align:left;padding:11px 14px;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:#86868b;border-bottom:1px solid #f2f2f7;white-space:nowrap}
td{padding:12px 14px;font-size:13px;border-bottom:1px solid #f2f2f7;white-space:nowrap}
td.name{max-width:220px;overflow:hidden;text-overflow:ellipsis}
tr.total td{border-bottom:none;font-weight:700;background:#f5f5f7}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:8px;vertical-align:middle}
.empty{color:#86868b;padding:20px;font-size:13px;display:block}
footer{text-align:center;padding:32px;font-size:12px;color:#aaa}
@media(max-width:640px){main{padding:20px 16px}header{padding:16px}th,td{padding:9px 10px}table{font-size:12px}.val{font-size:18px}}
</style>
</head>
<body>
<header>
  <h1>__CLIENT_NAME__</h1>
  <span class="upd">Updated __UPDATED_AT__</span>
</header>
<main>
  <div class="tabs" id="ptabs">
    <button class="tab active" onclick="setPeriod('ontem',this)">Yesterday</button>
    <button class="tab" onclick="setPeriod('d7',this)">Last 7 Days</button>
    <button class="tab" onclick="setPeriod('d30',this)">Last 30 Days</button>
    <button class="tab" onclick="setPeriod('mtd',this)">Month to Date</button>
    <button class="tab" onclick="setPeriod('last_month',this)">Last Month</button>
    <button class="tab" onclick="setPeriod('apr1',this)">Since April 1</button>
  </div>
  <div class="tabs vtabs">
    <button class="tab vtab active" onclick="setView('overview',this)">Overview</button>
    <button class="tab vtab" onclick="setView('campaigns',this)">Campaigns</button>
    <button class="tab vtab" onclick="setView('adsets',this)">Ad Sets</button>
    <button class="tab vtab" onclick="setView('ads',this)">Ads</button>
    <button class="tab vtab" onclick="setView('geo',this)">Geographic</button>
    <button class="tab vtab" onclick="setView('relatorio',this)">Report</button>
  </div>

  <div id="v-overview">
    <p class="sec">KPIs</p>
    <div class="grid" id="kpi"></div>
    <p class="sec">By Platform</p>
    <div class="tscroll">
      <table>
        <thead><tr>
          <th>Platform</th><th>Spend</th><th>Impressions</th><th>Clicks</th>
          <th>CPM</th><th>CPC</th><th>CTR</th>
          <th>Conv.</th><th>Revenue</th><th>CPA</th><th>ROAS</th>
        </tr></thead>
        <tbody id="ptable"></tbody>
      </table>
    </div>
    <p class="sec">Website — Google Analytics 4</p>
    <div class="grid" id="ga4"></div>
    <p class="sec">Orders — Store</p>
    <div class="grid" id="wc"></div>
  </div>

  <div id="v-campaigns" style="display:none">
    <p class="sec">Meta Ads — Campaigns</p>
    <div class="tscroll" id="c-meta"></div>
    <p class="sec">Google Ads — Campaigns</p>
    <div class="tscroll" id="c-google"></div>
    <p class="sec">TikTok Ads — Campaigns</p>
    <div class="tscroll" id="c-tiktok"></div>
    <p class="sec">LinkedIn Ads — Campaigns</p>
    <div class="tscroll" id="c-linkedin"></div>
  </div>

  <div id="v-adsets" style="display:none">
    <p class="sec">Meta Ads — Ad Sets</p>
    <div class="tscroll" id="as-meta"></div>
    <p class="sec">Google Ads — Ad Groups</p>
    <div class="tscroll" id="as-google"></div>
    <p class="sec">TikTok Ads — Ad Groups</p>
    <div class="tscroll" id="as-tiktok"></div>
    <p class="sec">LinkedIn Ads — Ad Groups</p>
    <div class="tscroll" id="as-linkedin"></div>
  </div>

  <div id="v-ads" style="display:none">
    <p class="sec">Meta Ads — Ads</p>
    <div class="tscroll" id="ad-meta"></div>
    <p class="sec">Google Ads — Ads</p>
    <div class="tscroll" id="ad-google"></div>
    <p class="sec">TikTok Ads — Ads</p>
    <div class="tscroll" id="ad-tiktok"></div>
    <p class="sec">LinkedIn Ads — Ads</p>
    <div class="tscroll" id="ad-linkedin"></div>
  </div>

  <div id="v-geo" style="display:none">
    <p class="sec">Meta Ads — By Country</p>
    <div class="tscroll" id="geo-meta"></div>
    <p class="sec">Google Ads — By Country</p>
    <div class="tscroll" id="geo-google"></div>
    <p class="sec">TikTok Ads — By Country</p>
    <div class="tscroll" id="geo-tiktok"></div>
    <p class="sec">LinkedIn Ads — By Country</p>
    <div class="tscroll" id="geo-linkedin"></div>
  </div>

  <div id="v-relatorio" style="display:none">
    <p class="sec">Email Report</p>
    <div style="margin-bottom:12px;display:flex;gap:8px;align-items:center">
      <button onclick="copyReport()" style="padding:8px 18px;border-radius:20px;font-size:13px;cursor:pointer;border:none;background:#111;color:#fff;font-weight:500">Copy text</button>
      <span id="copy-msg" style="font-size:12px;color:#34c759;display:none">Copied!</span>
    </div>
    <textarea id="report-text" readonly style="width:100%;height:520px;font-family:monospace;font-size:13px;background:#fff;border:1px solid #e5e5ea;border-radius:12px;padding:20px;resize:vertical;line-height:1.6"></textarea>
  </div>
</main>
<footer>Auto-updated dashboard · __UPDATED_AT__</footer>
<script>
const D = __DATA_JSON__;
let curPeriod = 'ontem', curView = 'overview';

const fmtUSD = v => '$' + (+v||0).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const fmtEUR = v => fmtUSD(v);
const fmt = (v, cur) => fmtUSD(v);
const num = v => Math.round(+v||0).toLocaleString('en-US');
const xr = v => (+v||0).toFixed(2) + 'x';
const pct = v => (+v||0).toFixed(2) + '%';
const card = (l, v, s, blue) => `<div class="card${blue?' blue':''}"><div class="lbl">${l}</div><div class="val">${v}</div>${s?`<div class="sub">${s}</div>`:''}</div>`;

function setPeriod(p, btn) {
  document.querySelectorAll('#ptabs .tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  curPeriod = p;
  renderView();
}

function setView(v, btn) {
  document.querySelectorAll('.vtab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('[id^="v-"]').forEach(el => el.style.display = 'none');
  document.getElementById('v-' + v).style.display = '';
  curView = v;
  renderView();
}

function renderView() {
  const data = D[curPeriod];
  ({overview: renderOverview, campaigns: renderCampaigns, adsets: renderAdsets, ads: renderAds, geo: renderGeo, relatorio: renderRelatorio})[curView](data);
}

function renderOverview(data) {
  const {meta: m, google_ads: g, tiktok_ads: tk, linkedin_ads: li, ga4, woocommerce: wc} = data;
  const mCur = m.currency || 'BRL', gCur = g.currency || 'BRL';
  const tkCur = (tk||{}).currency || 'BRL', liCur = (li||{}).currency || 'BRL';
  const wcCur = wc.currency || 'EUR';
  const sameCur = mCur === gCur;
  const blend = v => fmt(v, sameCur ? mCur : 'BRL');
  const ts = m.spend + g.spend + ((tk||{}).spend||0) + ((li||{}).spend||0);
  const tc = m.clicks + g.clicks + ((tk||{}).clicks||0) + ((li||{}).clicks||0);
  const ti = m.impressions + g.impressions + ((tk||{}).impressions||0) + ((li||{}).impressions||0);
  const tconv = (m.purchases || 0) + (g.conversions || 0) + ((tk||{}).conversions||0) + ((li||{}).conversions||0);
  const tr = m.revenue + g.revenue + ((tk||{}).revenue||0) + ((li||{}).revenue||0);

  document.getElementById('kpi').innerHTML = [
    card('Total Spend', blend(ts), sameCur ? 'Meta + Google Ads' : `Meta (${mCur}) + Google (${gCur})`, true),
    card('Revenue (Ads)', blend(tr), 'platform attribution'),
    card('Blended ROAS', xr(ts ? tr/ts : 0), 'return on ad spend'),
    card('Blended CPA', blend(tconv ? ts/tconv : 0), 'cost per conversion'),
    card('Blended CPM', blend(ti ? ts/ti*1000 : 0), 'cost per thousand impressions'),
    card('Blended CPC', blend(tc ? ts/tc : 0), 'cost per click'),
    card('Blended CTR', pct(ti ? tc/ti*100 : 0), 'click-through rate'),
    card('Conversions', num(tconv), 'attributed purchases'),
    card('Sessions (GA4)', num(ga4.sessions), 'website sessions'),
    card('Cost per Visit', blend(ga4.sessions ? ts/ga4.sessions : 0), 'spend / GA4 sessions'),
    card('Connect Rate', pct(tc ? ga4.sessions/tc*100 : 0), 'GA4 sessions / ad clicks'),
    card('Conversion Rate', pct(ga4.conversion_rate), 'GA4 — session → purchase'),
  ].join('');

  const prow = (color, name, d, conv, cur) => `<tr>
    <td><span class="dot" style="background:${color}"></span>${name}&nbsp;<small style="color:#86868b;font-size:10px">${cur}</small></td>
    <td>${fmt(d.spend,cur)}</td><td>${num(d.impressions)}</td><td>${num(d.clicks)}</td>
    <td>${fmt(d.cpm,cur)}</td><td>${fmt(d.cpc,cur)}</td><td>${pct(d.ctr)}</td>
    <td>${num(conv)}</td><td>${fmt(d.revenue,cur)}</td><td>${fmt(d.cpa,cur)}</td><td>${xr(d.roas)}</td>
  </tr>`;

  document.getElementById('ptable').innerHTML =
    prow('#0866ff','Meta Ads', m, m.purchases||0, mCur) +
    prow('#ea4335','Google Ads', g, g.conversions||0, gCur) +
    (tk&&tk.spend ? prow('#010101','TikTok Ads', tk, tk.conversions||0, tkCur) : '') +
    (li&&li.spend ? prow('#0a66c2','LinkedIn Ads', li, li.conversions||0, liCur) : '') +
    `<tr class="total"><td>Total</td>
    <td>${blend(ts)}</td><td>${num(ti)}</td><td>${num(tc)}</td>
    <td>${blend(ti?ts/ti*1000:0)}</td><td>${blend(tc?ts/tc:0)}</td><td>${pct(ti?tc/ti*100:0)}</td>
    <td>${num(tconv)}</td><td>${blend(tr)}</td><td>${blend(tconv?ts/tconv:0)}</td><td>${xr(ts?tr/ts:0)}</td>
    </tr>`;

  document.getElementById('ga4').innerHTML = [
    card('Sessions', num(ga4.sessions)),
    card('Users', num(ga4.users)),
    card('Transactions', num(ga4.transactions)),
    card('GA4 Revenue', fmt(ga4.revenue, wcCur)),
    card('Conversion Rate', pct(ga4.conversion_rate)),
  ].join('');

  document.getElementById('wc').innerHTML = [
    card('Orders', num(wc.orders)),
    card('Store Revenue', fmt(wc.revenue, wcCur)),
    card('Avg. Order Value', fmt(wc.avg_ticket, wcCur)),
  ].join('');
}

function brkTable(rows, cur, showCamp, showAdset) {
  if (!rows || !rows.length) return '<span class="empty">No data for this period</span>';
  const hdrs = ['Name', ...(showCamp?['Campaign']:[]), ...(showAdset?['Ad Set']:[]),
    'Spend','Impressions','Clicks','CPM','CPC','CTR','Conv.','Revenue','CPA','ROAS'];
  const getConv = d => d.conversions !== undefined ? d.conversions : (d.purchases || 0);
  const trs = rows.map(d => `<tr>
    <td class="name" title="${d.name}">${d.name}</td>
    ${showCamp ? `<td>${d.campaign||'—'}</td>` : ''}
    ${showAdset ? `<td>${d.adset||'—'}</td>` : ''}
    <td>${fmt(d.spend,cur)}</td><td>${num(d.impressions)}</td><td>${num(d.clicks)}</td>
    <td>${fmt(d.cpm,cur)}</td><td>${fmt(d.cpc,cur)}</td><td>${pct(d.ctr)}</td>
    <td>${num(getConv(d))}</td><td>${fmt(d.revenue,cur)}</td><td>${fmt(d.cpa,cur)}</td><td>${xr(d.roas)}</td>
  </tr>`).join('');
  return `<table><thead><tr>${hdrs.map(h=>`<th>${h}</th>`).join('')}</tr></thead><tbody>${trs}</tbody></table>`;
}

function geoTable(rows, cur) {
  if (!rows || !rows.length) return '<span class="empty">No data for this period</span>';
  const getConv = d => d.conversions !== undefined ? d.conversions : (d.purchases || 0);
  const trs = rows.map(d => `<tr>
    <td>${d.country}</td><td>${fmt(d.spend,cur)}</td><td>${num(d.impressions)}</td>
    <td>${num(d.clicks)}</td><td>${fmt(d.cpm,cur)}</td><td>${fmt(d.cpc,cur)}</td>
    <td>${pct(d.ctr)}</td><td>${num(getConv(d))}</td>
  </tr>`).join('');
  return `<table><thead><tr>
    <th>Country</th><th>Spend</th><th>Impressions</th><th>Clicks</th>
    <th>CPM</th><th>CPC</th><th>CTR</th><th>Conversions</th>
  </tr></thead><tbody>${trs}</tbody></table>`;
}

function renderCampaigns(data) {
  document.getElementById('c-meta').innerHTML = brkTable(data.meta_campaigns, data.meta.currency||'BRL', false, false);
  document.getElementById('c-google').innerHTML = brkTable(data.google_campaigns, data.google_ads.currency||'BRL', false, false);
  document.getElementById('c-tiktok').innerHTML = brkTable(data.tiktok_campaigns, (data.tiktok_ads||{}).currency||'BRL', false, false);
  document.getElementById('c-linkedin').innerHTML = brkTable(data.linkedin_campaigns, (data.linkedin_ads||{}).currency||'BRL', false, false);
}
function renderAdsets(data) {
  document.getElementById('as-meta').innerHTML = brkTable(data.meta_adsets, data.meta.currency||'BRL', true, false);
  document.getElementById('as-google').innerHTML = brkTable(data.google_adgroups, data.google_ads.currency||'BRL', true, false);
  document.getElementById('as-tiktok').innerHTML = brkTable(data.tiktok_adgroups, (data.tiktok_ads||{}).currency||'BRL', true, false);
  document.getElementById('as-linkedin').innerHTML = brkTable(data.linkedin_adgroups, (data.linkedin_ads||{}).currency||'BRL', true, false);
}
function renderAds(data) {
  document.getElementById('ad-meta').innerHTML = brkTable(data.meta_ads, data.meta.currency||'BRL', true, true);
  document.getElementById('ad-google').innerHTML = brkTable(data.google_ads_breakdown, data.google_ads.currency||'BRL', true, true);
  document.getElementById('ad-tiktok').innerHTML = brkTable(data.tiktok_ads_breakdown, (data.tiktok_ads||{}).currency||'BRL', true, true);
  document.getElementById('ad-linkedin').innerHTML = brkTable(data.linkedin_ads_breakdown, (data.linkedin_ads||{}).currency||'BRL', true, true);
}
function renderGeo(data) {
  document.getElementById('geo-meta').innerHTML = geoTable(data.meta_geo, data.meta.currency||'BRL');
  document.getElementById('geo-google').innerHTML = geoTable(data.google_geo, data.google_ads.currency||'BRL');
  document.getElementById('geo-tiktok').innerHTML = geoTable(data.tiktok_geo, (data.tiktok_ads||{}).currency||'BRL');
  document.getElementById('geo-linkedin').innerHTML = geoTable(data.linkedin_geo, (data.linkedin_ads||{}).currency||'BRL');
}

renderView();

function renderRelatorio(data) {
  const {meta: m, google_ads: g, tiktok_ads: tk, linkedin_ads: li, ga4, woocommerce: wc, meta_campaigns, google_campaigns, tiktok_campaigns, linkedin_campaigns, meta_adsets, google_adgroups, tiktok_adgroups, linkedin_adgroups, meta_ads, google_ads_breakdown, tiktok_ads_breakdown, linkedin_ads_breakdown} = data;
  const mCur = m.currency || 'BRL', gCur = g.currency || 'BRL';
  const tkCur = (tk||{}).currency || 'BRL', liCur = (li||{}).currency || 'BRL';
  const ts = m.spend + g.spend + ((tk||{}).spend||0) + ((li||{}).spend||0);
  const tr = m.revenue + g.revenue + ((tk||{}).revenue||0) + ((li||{}).revenue||0);
  const tconv = (m.purchases || 0) + (g.conversions || 0) + ((tk||{}).conversions||0) + ((li||{}).conversions||0);
  const tc = m.clicks + g.clicks + ((tk||{}).clicks||0) + ((li||{}).clicks||0);
  const ti = m.impressions + g.impressions + ((tk||{}).impressions||0) + ((li||{}).impressions||0);

  const b = (v, c) => '$' + (+v||0).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
  const n = v => Math.round(+v||0).toLocaleString('en-US');
  const p = v => (+v||0).toFixed(2) + '%';
  const x = v => (+v||0).toFixed(2) + 'x';
  const line = '━'.repeat(40);
  const dash = '—';

  const periodLabel = {ontem:'Yesterday',d7:'Last 7 Days',d30:'Last 30 Days',mtd:'Month to Date',last_month:'Last Month',apr1:'Since April 1st'}[curPeriod] || curPeriod;

  let r = '';
  r += 'PERFORMANCE REPORT\n';
  r += periodLabel.toUpperCase() + '\n';
  r += line + '\n\n';

  r += 'GENERAL SUMMARY\n';
  r += `Total Spend ............... ${b(ts,'BRL')}\n`;
  r += `  Meta Ads ................ ${b(m.spend,mCur)}\n`;
  r += `  Google Ads .............. ${b(g.spend,gCur)}\n`;
  if(tk&&tk.spend) r += `  TikTok Ads .............. ${b(tk.spend,tkCur)}\n`;
  if(li&&li.spend) r += `  LinkedIn Ads ............. ${b(li.spend,liCur)}\n`;
  r += `Revenue (attributed) ..... ${b(tr,'BRL')}\n`;
  r += `Blended ROAS .............. ${x(ts?tr/ts:0)}\n`;
  r += `Blended CPA ............... ${b(tconv?ts/tconv:0,'BRL')}\n`;
  r += `Total Conversions ......... ${n(tconv)}\n`;
  r += `Impressions ............... ${n(ti)}\n`;
  r += `Clicks .................... ${n(tc)}\n`;
  r += `Blended CTR ............... ${p(ti?tc/ti*100:0)}\n`;
  r += `Blended CPM ............... ${b(ti?ts/ti*1000:0,'BRL')}\n`;
  r += `Blended CPC ............... ${b(tc?ts/tc:0,'BRL')}\n\n`;

  r += line + '\n';
  r += 'META ADS\n';
  r += line + '\n';
  r += `Spend ..................... ${b(m.spend,mCur)}\n`;
  r += `Impressions ............... ${n(m.impressions)}\n`;
  r += `Clicks .................... ${n(m.clicks)}\n`;
  r += `CTR ....................... ${p(m.ctr)}\n`;
  r += `CPM ....................... ${b(m.cpm,mCur)}\n`;
  r += `CPC ....................... ${b(m.cpc,mCur)}\n`;
  r += `Purchases ................. ${n(m.purchases||0)}\n`;
  r += `Revenue ................... ${b(m.revenue,mCur)}\n`;
  r += `ROAS ...................... ${x(m.roas)}\n`;
  r += `CPA ....................... ${b(m.cpa,mCur)}\n`;
  r += `Reach ..................... ${n(m.reach||0)}\n\n`;

  if (meta_campaigns && meta_campaigns.length) {
    r += 'Meta Campaigns (top ' + Math.min(meta_campaigns.length,5) + '):\n';
    meta_campaigns.slice(0,5).forEach((c,i) => {
      r += `  ${i+1}. ${c.name}\n`;
      r += `     Spend: ${b(c.spend,mCur)} | ROAS: ${x(c.roas)} | Purchases: ${n(c.purchases||0)} | CPA: ${b(c.cpa,mCur)}\n`;
    });
    r += '\n';
  }

  if (meta_adsets && meta_adsets.length) {
    r += 'Meta Ad Sets (top ' + Math.min(meta_adsets.length,5) + '):\n';
    meta_adsets.slice(0,5).forEach((c,i) => {
      r += `  ${i+1}. ${c.name}\n`;
      r += `     Spend: ${b(c.spend,mCur)} | CTR: ${p(c.ctr)} | CPC: ${b(c.cpc,mCur)} | Purchases: ${n(c.purchases||0)}\n`;
    });
    r += '\n';
  }

  if (meta_ads && meta_ads.length) {
    r += 'Meta Ads (top ' + Math.min(meta_ads.length,5) + '):\n';
    meta_ads.slice(0,5).forEach((c,i) => {
      r += `  ${i+1}. ${c.name}\n`;
      r += `     Campaign: ${c.campaign||dash} | Ad Set: ${c.adset||dash}\n`;
      r += `     Spend: ${b(c.spend,mCur)} | CTR: ${p(c.ctr)} | Purchases: ${n(c.purchases||0)} | ROAS: ${x(c.roas)}\n`;
    });
    r += '\n';
  }

  r += line + '\n';
  r += 'GOOGLE ADS\n';
  r += line + '\n';
  r += `Spend ..................... ${b(g.spend,gCur)}\n`;
  r += `Impressions ............... ${n(g.impressions)}\n`;
  r += `Clicks .................... ${n(g.clicks)}\n`;
  r += `CTR ....................... ${p(g.ctr)}\n`;
  r += `CPM ....................... ${b(g.cpm,gCur)}\n`;
  r += `CPC ....................... ${b(g.cpc,gCur)}\n`;
  r += `Conversions ............... ${n(g.conversions||0)}\n`;
  r += `Revenue ................... ${b(g.revenue,gCur)}\n`;
  r += `ROAS ...................... ${x(g.roas)}\n`;
  r += `CPA ....................... ${b(g.cpa,gCur)}\n\n`;

  if (google_campaigns && google_campaigns.length) {
    r += 'Google Campaigns (top ' + Math.min(google_campaigns.length,5) + '):\n';
    google_campaigns.slice(0,5).forEach((c,i) => {
      r += `  ${i+1}. ${c.name} [${c.status}]\n`;
      r += `     Spend: ${b(c.spend,gCur)} | ROAS: ${x(c.roas)} | Conv.: ${n(c.conversions||0)} | CPA: ${b(c.cpa,gCur)}\n`;
    });
    r += '\n';
  }

  if (google_adgroups && google_adgroups.length) {
    r += 'Google Ad Groups (top ' + Math.min(google_adgroups.length,5) + '):\n';
    google_adgroups.slice(0,5).forEach((c,i) => {
      r += `  ${i+1}. ${c.name}\n`;
      r += `     Campaign: ${c.campaign||dash} | Spend: ${b(c.spend,gCur)} | CTR: ${p(c.ctr)} | Conv.: ${n(c.conversions||0)}\n`;
    });
    r += '\n';
  }


  if (tk && tk.spend) {
    r += line + '\n';
    r += 'TIKTOK ADS\n';
    r += line + '\n';
    r += `Spend ..................... ${b(tk.spend,tkCur)}\n`;
    r += `Impressions ............... ${n(tk.impressions||0)}\n`;
    r += `Clicks .................... ${n(tk.clicks||0)}\n`;
    r += `CTR ....................... ${p(tk.ctr||0)}\n`;
    r += `CPM ....................... ${b(tk.cpm||0,tkCur)}\n`;
    r += `CPC ....................... ${b(tk.cpc||0,tkCur)}\n`;
    r += `Conversions ............... ${n(tk.conversions||0)}\n`;
    r += `Revenue ................... ${b(tk.revenue||0,tkCur)}\n`;
    r += `ROAS ...................... ${x(tk.roas||0)}\n`;
    r += `CPA ....................... ${b(tk.cpa||0,tkCur)}\n`;
    if (tiktok_campaigns && tiktok_campaigns.length) {
      r += 'TikTok Campaigns (top ' + Math.min(tiktok_campaigns.length,5) + '):\n';
      tiktok_campaigns.slice(0,5).forEach((c,i) => {
        r += `  ${i+1}. ${c.name}\n`;
        r += `     Spend: ${b(c.spend,tkCur)} | ROAS: ${x(c.roas)} | Conv.: ${n(c.conversions||0)} | CPA: ${b(c.cpa,tkCur)}\n`;
      });
    }
    r += '\n';
  }

  if (li && li.spend) {
    r += line + '\n';
    r += 'LINKEDIN ADS\n';
    r += line + '\n';
    r += `Spend ..................... ${b(li.spend,liCur)}\n`;
    r += `Impressions ............... ${n(li.impressions||0)}\n`;
    r += `Clicks .................... ${n(li.clicks||0)}\n`;
    r += `CTR ....................... ${p(li.ctr||0)}\n`;
    r += `CPM ....................... ${b(li.cpm||0,liCur)}\n`;
    r += `CPC ....................... ${b(li.cpc||0,liCur)}\n`;
    r += `Conversions ............... ${n(li.conversions||0)}\n`;
    r += `Revenue ................... ${b(li.revenue||0,liCur)}\n`;
    r += `ROAS ...................... ${x(li.roas||0)}\n`;
    r += `CPA ....................... ${b(li.cpa||0,liCur)}\n`;
    if (linkedin_campaigns && linkedin_campaigns.length) {
      r += 'LinkedIn Campaigns (top ' + Math.min(linkedin_campaigns.length,5) + '):\n';
      linkedin_campaigns.slice(0,5).forEach((c,i) => {
        r += `  ${i+1}. ${c.name}\n`;
        r += `     Spend: ${b(c.spend,liCur)} | ROAS: ${x(c.roas)} | Conv.: ${n(c.conversions||0)} | CPA: ${b(c.cpa,liCur)}\n`;
      });
    }
    r += '\n';
  }

  r += line + '\n';
  r += 'GOOGLE ANALYTICS 4\n';
  r += line + '\n';
  r += `Sessions .................. ${n(ga4.sessions)}\n`;
  r += `Users ..................... ${n(ga4.users)}\n`;
  r += `Transactions .............. ${n(ga4.transactions)}\n`;
  r += `GA4 Revenue ............... ${b(ga4.revenue,'USD')}\n`;
  r += `Conversion Rate ........... ${p(ga4.conversion_rate)}\n`;
  r += `Cost per Visit ............ ${b(ga4.sessions?ts/ga4.sessions:0,'USD')}\n`;
  r += `Connect Rate .............. ${p(tc?ga4.sessions/tc*100:0)}\n\n`;

  r += line + '\n';
  r += 'STORE (WOOCOMMERCE)\n';
  r += line + '\n';
  r += `Orders .................... ${n(wc.orders)}\n`;
  r += `Revenue ................... ${b(wc.revenue,'BRL')}\n`;
  r += `Avg. Order Value .......... ${b(wc.avg_ticket,'BRL')}\n\n`;

  r += line + '\n';
  r += `Generated on: ${new Date().toLocaleString('en-US')}\n`;

  document.getElementById('report-text').value = r;
}

function copyReport() {
  const ta = document.getElementById('report-text');
  ta.select();
  navigator.clipboard.writeText(ta.value).then(() => {
    const msg = document.getElementById('copy-msg');
    msg.style.display = 'inline';
    setTimeout(() => msg.style.display = 'none', 2000);
  });
}
</script>
</body>
</html>"""


def _fetch_period(since, until):
    return {
        "meta": fetch_meta(since, until),
        "google_ads": fetch_google_ads(since, until),
        "tiktok_ads": fetch_tiktok(since, until),
        "linkedin_ads": fetch_linkedin(since, until),
        "meta_campaigns": fetch_meta_breakdown(since, until, "campaign"),
        "meta_adsets": fetch_meta_breakdown(since, until, "adset"),
        "meta_ads": fetch_meta_breakdown(since, until, "ad"),
        "google_campaigns": fetch_google_campaigns(since, until),
        "google_adgroups": fetch_google_adgroups(since, until),
        "google_ads_breakdown": fetch_google_ads_breakdown(since, until),
        "tiktok_campaigns": fetch_tiktok_breakdown(since, until, "campaign"),
        "tiktok_adgroups": fetch_tiktok_breakdown(since, until, "adset"),
        "tiktok_ads_breakdown": fetch_tiktok_breakdown(since, until, "ad"),
        "linkedin_campaigns": fetch_linkedin_breakdown(since, until, "campaign"),
        "linkedin_adgroups": fetch_linkedin_breakdown(since, until, "adset"),
        "linkedin_ads_breakdown": fetch_linkedin_breakdown(since, until, "ad"),
        "meta_geo": fetch_meta_geo(since, until),
        "google_geo": fetch_google_geo(since, until),
        "tiktok_geo": fetch_tiktok_geo(since, until),
        "linkedin_geo": fetch_linkedin_geo(since, until),
        "ga4": fetch_ga4(since, until),
        "woocommerce": fetch_woocommerce(since, until),
    }


def main():
    today = datetime.now()
    yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    d7_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    d30_start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    mtd_start = today.replace(day=1).strftime("%Y-%m-%d")
    last_month_end = today.replace(day=1) - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")

    print("Fetching data...")
    apr1_start = today.replace(month=4, day=1).strftime("%Y-%m-%d")

    data = {
        "ontem": _fetch_period(yesterday, yesterday),
        "d7": _fetch_period(d7_start, today_str),
        "d30": _fetch_period(d30_start, today_str),
        "mtd": _fetch_period(mtd_start, today_str),
        "last_month": _fetch_period(last_month_start, last_month_end.strftime("%Y-%m-%d")),
        "apr1": _fetch_period(apr1_start, today_str),
    }

    client_name = "Dashboard"
    updated_at = today.strftime("%d/%m/%Y %H:%M")

    html = (
        HTML
        .replace("__CLIENT_NAME__", client_name)
        .replace("__UPDATED_AT__", updated_at)
        .replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))
    )

    out = os.path.join(os.path.dirname(os.path.dirname(__file__)), "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Generated: index.html ({updated_at})")


if __name__ == "__main__":
    main()
