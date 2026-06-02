#!/usr/bin/env python3
import json
import os
import requests
from datetime import datetime, timedelta

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Metric, RunReportRequest
from google.oauth2 import service_account
from woocommerce import API as WcAPI


_meta_currency_cache = None
_google_setup_cache = None


# ── Meta Ads ──────────────────────────────────────────────────────────────────

def _meta_currency():
    global _meta_currency_cache
    if _meta_currency_cache:
        return _meta_currency_cache
    try:
        r = requests.get(
            f"https://graph.facebook.com/v19.0/{os.environ['META_ACCOUNT_ID']}",
            params={"access_token": os.environ["META_ACCESS_TOKEN"], "fields": "currency"},
            timeout=10,
        )
        _meta_currency_cache = r.json().get("currency", "BRL")
    except Exception:
        _meta_currency_cache = "BRL"
    return _meta_currency_cache


def _parse_meta_row(d):
    spend = float(d.get("spend", 0))
    imp = int(d.get("impressions", 0))
    clicks = int(d.get("clicks", 0))
    actions = {a["action_type"]: float(a["value"]) for a in d.get("actions", [])}
    avals = {a["action_type"]: float(a["value"]) for a in d.get("action_values", [])}
    purchases = int(actions.get("purchase", 0))
    revenue = avals.get("purchase", 0.0)
    return {
        "spend": spend,
        "impressions": imp,
        "clicks": clicks,
        "reach": int(d.get("reach", 0)),
        "cpm": float(d.get("cpm", spend / imp * 1000 if imp else 0)),
        "cpc": float(d.get("cpc", spend / clicks if clicks else 0)),
        "ctr": float(d.get("ctr", clicks / imp * 100 if imp else 0)),
        "purchases": purchases,
        "revenue": revenue,
        "cpa": spend / purchases if purchases else 0,
        "roas": revenue / spend if spend else 0,
    }


def fetch_meta(since, until):
    try:
        tok = os.environ["META_ACCESS_TOKEN"]
        acc = os.environ["META_ACCOUNT_ID"]
        r = requests.get(
            f"https://graph.facebook.com/v19.0/{acc}/insights",
            params={
                "access_token": tok,
                "fields": "spend,impressions,clicks,reach,actions,action_values,cpc,ctr,cpm",
                "time_range": json.dumps({"since": since, "until": until}),
                "level": "account",
            },
            timeout=30,
        )
        raw = r.json().get("data", [])
        result = _parse_meta_row(raw[0] if raw else {})
        result["currency"] = _meta_currency()
        return result
    except Exception as e:
        print(f"[Meta] {e}")
        return {"spend": 0, "impressions": 0, "clicks": 0, "reach": 0, "cpm": 0, "cpc": 0, "ctr": 0, "purchases": 0, "revenue": 0, "cpa": 0, "roas": 0, "currency": "BRL"}


def fetch_meta_breakdown(since, until, level):
    try:
        tok = os.environ["META_ACCESS_TOKEN"]
        acc = os.environ["META_ACCOUNT_ID"]
        name_key = {"campaign": "campaign_name", "adset": "adset_name", "ad": "ad_name"}[level]
        r = requests.get(
            f"https://graph.facebook.com/v19.0/{acc}/insights",
            params={
                "access_token": tok,
                "fields": "campaign_name,adset_name,ad_name,spend,impressions,clicks,reach,cpc,ctr,cpm,actions,action_values",
                "time_range": json.dumps({"since": since, "until": until}),
                "level": level,
                "limit": 50,
            },
            timeout=30,
        )
        rows = []
        for d in r.json().get("data", []):
            row = _parse_meta_row(d)
            row["name"] = d.get(name_key, "—")
            if level in ("adset", "ad"):
                row["campaign"] = d.get("campaign_name", "—")
            if level == "ad":
                row["adset"] = d.get("adset_name", "—")
            rows.append(row)
        rows.sort(key=lambda x: x["spend"], reverse=True)
        return rows
    except Exception as e:
        print(f"[Meta {level}] {e}")
        return []


def fetch_meta_geo(since, until):
    try:
        tok = os.environ["META_ACCESS_TOKEN"]
        acc = os.environ["META_ACCOUNT_ID"]
        r = requests.get(
            f"https://graph.facebook.com/v19.0/{acc}/insights",
            params={
                "access_token": tok,
                "fields": "spend,impressions,clicks,cpc,ctr,cpm,actions,action_values",
                "time_range": json.dumps({"since": since, "until": until}),
                "breakdowns": "country",
                "level": "account",
                "limit": 30,
            },
            timeout=30,
        )
        rows = []
        for d in r.json().get("data", []):
            row = _parse_meta_row(d)
            row["country"] = d.get("country", "—")
            rows.append(row)
        rows.sort(key=lambda x: x["spend"], reverse=True)
        return rows
    except Exception as e:
        print(f"[Meta Geo] {e}")
        return []


# ── Google Ads ─────────────────────────────────────────────────────────────────

def _google_setup():
    global _google_setup_cache
    if _google_setup_cache:
        return _google_setup_cache
    tok = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "refresh_token": os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
            "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"],
            "grant_type": "refresh_token",
        },
        timeout=15,
    ).json()
    if "access_token" not in tok:
        raise RuntimeError(f"token failed: {tok.get('error')}")
    cid = os.environ["GOOGLE_ADS_CUSTOMER_ID"].replace("-", "").strip()
    headers = {
        "Authorization": f"Bearer {tok['access_token']}",
        "developer-token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"].strip(),
        "Content-Type": "application/json",
    }
    login = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "").strip()
    if login:
        headers["login-customer-id"] = login
    _google_setup_cache = (cid, headers)
    return _google_setup_cache


def _gads_query(query):
    cid, headers = _google_setup()
    r = requests.post(
        f"https://googleads.googleapis.com/v20/customers/{cid}/googleAds:search",
        headers=headers, json={"query": query}, timeout=30,
    )
    data = r.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("message", str(data["error"])))
    return data.get("results", [])


def _google_currency():
    try:
        res = _gads_query("SELECT customer.currency_code FROM customer LIMIT 1")
        if res:
            return res[0].get("customer", {}).get("currencyCode", "BRL")
    except Exception:
        pass
    return "BRL"


def _parse_gads(m):
    cost = int(m.get("costMicros", 0)) / 1_000_000
    imp = int(m.get("impressions", 0))
    clicks = int(m.get("clicks", 0))
    conv = float(m.get("conversions", 0))
    rev = float(m.get("conversionsValue", 0))
    return {
        "spend": cost,
        "impressions": imp,
        "clicks": clicks,
        "cpm": cost / imp * 1000 if imp else 0,
        "cpc": cost / clicks if clicks else 0,
        "ctr": clicks / imp * 100 if imp else 0,
        "conversions": int(conv),
        "revenue": rev,
        "cpa": cost / conv if conv else 0,
        "roas": rev / cost if cost else 0,
    }


def fetch_google_ads(since, until):
    try:
        results = _gads_query(
            f"SELECT metrics.cost_micros,metrics.impressions,metrics.clicks,"
            f"metrics.conversions,metrics.conversions_value"
            f" FROM customer WHERE segments.date BETWEEN '{since}' AND '{until}'"
        )
        totals = {"costMicros": 0, "impressions": 0, "clicks": 0, "conversions": 0.0, "conversionsValue": 0.0}
        for r in results:
            m = r.get("metrics", {})
            totals["costMicros"] += int(m.get("costMicros", 0))
            totals["impressions"] += int(m.get("impressions", 0))
            totals["clicks"] += int(m.get("clicks", 0))
            totals["conversions"] += float(m.get("conversions", 0))
            totals["conversionsValue"] += float(m.get("conversionsValue", 0))
        result = _parse_gads(totals)
        result["currency"] = _google_currency()
        return result
    except Exception as e:
        print(f"[Google Ads] {e}")
        return {"spend": 0, "impressions": 0, "clicks": 0, "cpm": 0, "cpc": 0, "ctr": 0, "conversions": 0, "revenue": 0, "cpa": 0, "roas": 0, "currency": "BRL"}


def fetch_google_campaigns(since, until):
    try:
        results = _gads_query(
            f"SELECT campaign.name,campaign.status,metrics.cost_micros,metrics.impressions,"
            f"metrics.clicks,metrics.conversions,metrics.conversions_value"
            f" FROM campaign WHERE segments.date BETWEEN '{since}' AND '{until}'"
            f" ORDER BY metrics.cost_micros DESC LIMIT 50"
        )
        rows = []
        for r in results:
            row = _parse_gads(r.get("metrics", {}))
            c = r.get("campaign", {})
            row["name"] = c.get("name", "—")
            row["status"] = c.get("status", "—")
            rows.append(row)
        return rows
    except Exception as e:
        print(f"[Google Campaigns] {e}")
        return []


def fetch_google_adgroups(since, until):
    try:
        results = _gads_query(
            f"SELECT ad_group.name,ad_group.status,campaign.name,metrics.cost_micros,"
            f"metrics.impressions,metrics.clicks,metrics.conversions,metrics.conversions_value"
            f" FROM ad_group WHERE segments.date BETWEEN '{since}' AND '{until}'"
            f" ORDER BY metrics.cost_micros DESC LIMIT 50"
        )
        rows = []
        for r in results:
            row = _parse_gads(r.get("metrics", {}))
            ag = r.get("adGroup", {})
            row["name"] = ag.get("name", "—")
            row["status"] = ag.get("status", "—")
            row["campaign"] = r.get("campaign", {}).get("name", "—")
            rows.append(row)
        return rows
    except Exception as e:
        print(f"[Google AdGroups] {e}")
        return []


def fetch_google_ads_breakdown(since, until):
    try:
        results = _gads_query(
            f"SELECT ad_group_ad.ad.name,ad_group_ad.ad.id,ad_group_ad.status,"
            f"campaign.name,ad_group.name,metrics.cost_micros,metrics.impressions,"
            f"metrics.clicks,metrics.conversions,metrics.conversions_value"
            f" FROM ad_group_ad WHERE segments.date BETWEEN '{since}' AND '{until}'"
            f" ORDER BY metrics.cost_micros DESC LIMIT 50"
        )
        rows = []
        for r in results:
            row = _parse_gads(r.get("metrics", {}))
            ad = r.get("adGroupAd", {})
            ad_info = ad.get("ad", {})
            row["name"] = ad_info.get("name", "") or str(ad_info.get("id", "—"))
            row["status"] = ad.get("status", "—")
            row["campaign"] = r.get("campaign", {}).get("name", "—")
            row["adset"] = r.get("adGroup", {}).get("name", "—")
            rows.append(row)
        return rows
    except Exception as e:
        print(f"[Google Ads breakdown] {e}")
        return []


_GEO = {
    "2076": "Brasil", "2840": "EUA", "2620": "Portugal", "2032": "Argentina",
    "2152": "Chile", "2170": "Colômbia", "2858": "Uruguai", "2604": "Peru",
    "2276": "Alemanha", "2250": "França", "2724": "Espanha", "2380": "Itália",
    "2826": "Reino Unido", "2528": "Países Baixos", "2036": "Austrália",
    "2124": "Canadá", "2392": "Japão", "2156": "China", "2710": "África do Sul",
    "2484": "México",
}


def fetch_google_geo(since, until):
    try:
        results = _gads_query(
            f"SELECT geographic_view.country_criterion_id,metrics.cost_micros,"
            f"metrics.impressions,metrics.clicks,metrics.conversions,metrics.conversions_value"
            f" FROM geographic_view WHERE segments.date BETWEEN '{since}' AND '{until}'"
            f" ORDER BY metrics.cost_micros DESC LIMIT 30"
        )
        agg = {}
        for r in results:
            gv = r.get("geographicView", {})
            cid = str(gv.get("countryCriterionId", "") or "")
            if not cid:
                continue
            m = r.get("metrics", {})
            if cid not in agg:
                agg[cid] = {"costMicros": 0, "impressions": 0, "clicks": 0, "conversions": 0.0, "conversionsValue": 0.0}
            agg[cid]["costMicros"] += int(m.get("costMicros", 0))
            agg[cid]["impressions"] += int(m.get("impressions", 0))
            agg[cid]["clicks"] += int(m.get("clicks", 0))
            agg[cid]["conversions"] += float(m.get("conversions", 0))
            agg[cid]["conversionsValue"] += float(m.get("conversionsValue", 0))
        rows = []
        for cid, totals in agg.items():
            row = _parse_gads(totals)
            row["country"] = _GEO.get(cid, f"ID:{cid}")
            rows.append(row)
        rows.sort(key=lambda x: x["spend"], reverse=True)
        return rows
    except Exception as e:
        print(f"[Google Geo] {e}")
        return []


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
    try:
        refresh_token = os.environ.get("GA4_REFRESH_TOKEN", "").strip()
        if refresh_token:
            tok = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "refresh_token": refresh_token,
                    "client_id": os.environ.get("GA4_CLIENT_ID", os.environ["GOOGLE_ADS_CLIENT_ID"]).strip(),
                    "client_secret": os.environ.get("GA4_CLIENT_SECRET", os.environ["GOOGLE_ADS_CLIENT_SECRET"]).strip(),
                    "grant_type": "refresh_token",
                },
                timeout=15,
            ).json()
            if "access_token" not in tok:
                raise RuntimeError(f"token failed: {tok.get('error')}")
            return _ga4_via_rest(since, until, tok["access_token"])
        creds = service_account.Credentials.from_service_account_info(
            json.loads(os.environ["GA4_CREDENTIALS_JSON"]),
            scopes=["https://www.googleapis.com/auth/analytics.readonly"],
        )
        client = BetaAnalyticsDataClient(credentials=creds)
        resp = client.run_report(RunReportRequest(
            property=f"properties/{os.environ['GA4_PROPERTY_ID'].strip()}",
            date_ranges=[DateRange(start_date=since, end_date=until)],
            metrics=[
                Metric(name="sessions"), Metric(name="totalUsers"), Metric(name="transactions"),
                Metric(name="purchaseRevenue"), Metric(name="sessionConversionRate"),
            ],
        ))
        if not resp.rows:
            return {"sessions": 0, "users": 0, "transactions": 0, "revenue": 0.0, "conversion_rate": 0.0}
        v = [mv.value for mv in resp.rows[0].metric_values]
        return {"sessions": int(v[0]), "users": int(v[1]), "transactions": int(v[2]), "revenue": float(v[3]), "conversion_rate": float(v[4]) * 100}
    except Exception as e:
        print(f"[GA4] {e}")
        return {"sessions": 0, "users": 0, "transactions": 0, "revenue": 0.0, "conversion_rate": 0.0}


# ── WooCommerce ─────────────────────────────────────────────────────────────────

def fetch_woocommerce(since, until):
    try:
        wc = WcAPI(
            url=os.environ["WC_STORE_URL"],
            consumer_key=os.environ["WC_CONSUMER_KEY"],
            consumer_secret=os.environ["WC_CONSUMER_SECRET"],
            version="wc/v3",
            timeout=30,
        )
        try:
            cur_resp = wc.get("settings/general/woocommerce_currency").json()
            currency = cur_resp.get("value", "EUR") if isinstance(cur_resp, dict) else "EUR"
        except Exception:
            currency = "EUR"
        all_orders = []
        for status in ["completed", "processing", "on-hold"]:
            page = 1
            while True:
                resp = wc.get("orders", params={
                    "after": since + "T00:00:00",
                    "before": until + "T23:59:59",
                    "status": status,
                    "per_page": 100,
                    "page": page,
                }).json()
                if not isinstance(resp, list) or not resp:
                    break
                all_orders.extend(resp)
                if len(resp) < 100:
                    break
                page += 1
        if not all_orders:
            return {"orders": 0, "revenue": 0.0, "avg_ticket": 0.0, "currency": currency}
        rev = sum(float(o.get("total", 0)) for o in all_orders)
        n = len(all_orders)
        return {"orders": n, "revenue": rev, "avg_ticket": rev / n if n else 0, "currency": currency}
    except Exception as e:
        print(f"[WooCommerce] {e}")
        return {"orders": 0, "revenue": 0.0, "avg_ticket": 0.0, "currency": "EUR"}


# ── HTML template ──────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="pt-BR"><head>
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
  <span class="upd">Atualizado __UPDATED_AT__</span>
</header>
<main>
  <div class="tabs" id="ptabs">
    <button class="tab active" onclick="setPeriod('ontem',this)">Ontem</button>
    <button class="tab" onclick="setPeriod('d7',this)">Últimos 7 dias</button>
    <button class="tab" onclick="setPeriod('d30',this)">Últimos 30 dias</button>
    <button class="tab" onclick="setPeriod('mtd',this)">Mês até hoje</button>
    <button class="tab" onclick="setPeriod('last_month',this)">Mês passado</button>
    <button class="tab" onclick="setPeriod('apr1',this)">Desde 1º de Abril</button>
  </div>
  <div class="tabs vtabs">
    <button class="tab vtab active" onclick="setView('overview',this)">Visão Geral</button>
    <button class="tab vtab" onclick="setView('campaigns',this)">Campanhas</button>
    <button class="tab vtab" onclick="setView('adsets',this)">Conjuntos</button>
    <button class="tab vtab" onclick="setView('ads',this)">Anúncios</button>
    <button class="tab vtab" onclick="setView('geo',this)">Geográfico</button>
    <button class="tab vtab" onclick="setView('relatorio',this)">Relatório</button>
  </div>

  <div id="v-overview">
    <p class="sec">KPIs</p>
    <div class="grid" id="kpi"></div>
    <p class="sec">Por Plataforma</p>
    <div class="tscroll">
      <table>
        <thead><tr>
          <th>Plataforma</th><th>Investido</th><th>Impressões</th><th>Cliques</th>
          <th>CPM</th><th>CPC</th><th>CTR</th>
          <th>Conversões</th><th>Receita</th><th>CPA</th><th>ROAS</th>
        </tr></thead>
        <tbody id="ptable"></tbody>
      </table>
    </div>
    <p class="sec">Site — Google Analytics 4</p>
    <div class="grid" id="ga4"></div>
    <p class="sec">Pedidos — Loja</p>
    <div class="grid" id="wc"></div>
  </div>

  <div id="v-campaigns" style="display:none">
    <p class="sec">Meta Ads — Campanhas</p>
    <div class="tscroll" id="c-meta"></div>
    <p class="sec">Google Ads — Campanhas</p>
    <div class="tscroll" id="c-google"></div>
  </div>

  <div id="v-adsets" style="display:none">
    <p class="sec">Meta Ads — Conjuntos de Anúncios</p>
    <div class="tscroll" id="as-meta"></div>
    <p class="sec">Google Ads — Grupos de Anúncios</p>
    <div class="tscroll" id="as-google"></div>
  </div>

  <div id="v-ads" style="display:none">
    <p class="sec">Meta Ads — Anúncios</p>
    <div class="tscroll" id="ad-meta"></div>
    <p class="sec">Google Ads — Anúncios</p>
    <div class="tscroll" id="ad-google"></div>
  </div>

  <div id="v-geo" style="display:none">
    <p class="sec">Meta Ads — Por País</p>
    <div class="tscroll" id="geo-meta"></div>
    <p class="sec">Google Ads — Por País</p>
    <div class="tscroll" id="geo-google"></div>
  </div>

  <div id="v-relatorio" style="display:none">
    <p class="sec">Relatório para E-mail</p>
    <div style="margin-bottom:12px;display:flex;gap:8px;align-items:center">
      <button onclick="copyReport()" style="padding:8px 18px;border-radius:20px;font-size:13px;cursor:pointer;border:none;background:#111;color:#fff;font-weight:500">Copiar texto</button>
      <span id="copy-msg" style="font-size:12px;color:#34c759;display:none">Copiado!</span>
    </div>
    <textarea id="report-text" readonly style="width:100%;height:520px;font-family:monospace;font-size:13px;background:#fff;border:1px solid #e5e5ea;border-radius:12px;padding:20px;resize:vertical;line-height:1.6"></textarea>
  </div>
</main>
<footer>Dashboard gerado automaticamente · __UPDATED_AT__</footer>
<script>
const D = __DATA_JSON__;
let curPeriod = 'ontem', curView = 'overview';

const fmtBRL = v => 'R$ ' + (+v||0).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2});
const fmtEUR = v => '€ ' + (+v||0).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2});
const fmt = (v, cur) => cur === 'EUR' ? fmtEUR(v) : fmtBRL(v);
const num = v => Math.round(+v||0).toLocaleString('pt-BR');
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
  const {meta: m, google_ads: g, ga4, woocommerce: wc} = data;
  const mCur = m.currency || 'BRL', gCur = g.currency || 'BRL';
  const sameCur = mCur === gCur;
  const blend = v => fmt(v, sameCur ? mCur : 'BRL');
  const ts = m.spend + g.spend, tc = m.clicks + g.clicks, ti = m.impressions + g.impressions;
  const tconv = (m.purchases || 0) + (g.conversions || 0), tr = m.revenue + g.revenue;

  document.getElementById('kpi').innerHTML = [
    card('Total Investido', blend(ts), sameCur ? 'Meta + Google Ads' : `Meta (${mCur}) + Google (${gCur})`, true),
    card('Receita (Ads)', blend(tr), 'atribuição das plataformas'),
    card('ROAS Blendado', xr(ts ? tr/ts : 0), 'retorno sobre investimento'),
    card('CPA Blendado', blend(tconv ? ts/tconv : 0), 'custo por conversão'),
    card('CPM Blendado', blend(ti ? ts/ti*1000 : 0), 'custo por mil impressões'),
    card('CPC Blendado', blend(tc ? ts/tc : 0), 'custo por clique'),
    card('CTR Blendado', pct(ti ? tc/ti*100 : 0), 'taxa de clique'),
    card('Conversões', num(tconv), 'compras atribuídas'),
    card('Visitas (GA4)', num(ga4.sessions), 'sessões no site'),
    card('Custo por Visita', blend(ga4.sessions ? ts/ga4.sessions : 0), 'investimento / sessões GA4'),
    card('Connect Rate', pct(tc ? ga4.sessions/tc*100 : 0), 'sessões GA4 / cliques nos ads'),
    card('Taxa de Conversão', pct(ga4.conversion_rate), 'GA4 — sessão → compra'),
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
    `<tr class="total"><td>Total</td>
    <td>${blend(ts)}</td><td>${num(ti)}</td><td>${num(tc)}</td>
    <td>${blend(ti?ts/ti*1000:0)}</td><td>${blend(tc?ts/tc:0)}</td><td>${pct(ti?tc/ti*100:0)}</td>
    <td>${num(tconv)}</td><td>${blend(tr)}</td><td>${blend(tconv?ts/tconv:0)}</td><td>${xr(ts?tr/ts:0)}</td>
    </tr>`;

  document.getElementById('ga4').innerHTML = [
    card('Sessões', num(ga4.sessions)),
    card('Usuários', num(ga4.users)),
    card('Transações', num(ga4.transactions)),
    card('Receita GA4', fmt(ga4.revenue, wcCur)),
    card('Taxa de Conversão', pct(ga4.conversion_rate)),
  ].join('');

  const wcCur = wc.currency || 'EUR';
  document.getElementById('wc').innerHTML = [
    card('Pedidos', num(wc.orders)),
    card('Receita Loja', fmt(wc.revenue, wcCur)),
    card('Ticket Médio', fmt(wc.avg_ticket, wcCur)),
  ].join('');
}

function brkTable(rows, cur, showCamp, showAdset) {
  if (!rows || !rows.length) return '<span class="empty">Sem dados para o período</span>';
  const hdrs = ['Nome', ...(showCamp?['Campanha']:[]), ...(showAdset?['Conjunto']:[]),
    'Investido','Impressões','Cliques','CPM','CPC','CTR','Conv.','Receita','CPA','ROAS'];
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
  if (!rows || !rows.length) return '<span class="empty">Sem dados para o período</span>';
  const getConv = d => d.conversions !== undefined ? d.conversions : (d.purchases || 0);
  const trs = rows.map(d => `<tr>
    <td>${d.country}</td><td>${fmt(d.spend,cur)}</td><td>${num(d.impressions)}</td>
    <td>${num(d.clicks)}</td><td>${fmt(d.cpm,cur)}</td><td>${fmt(d.cpc,cur)}</td>
    <td>${pct(d.ctr)}</td><td>${num(getConv(d))}</td>
  </tr>`).join('');
  return `<table><thead><tr>
    <th>País</th><th>Investido</th><th>Impressões</th><th>Cliques</th>
    <th>CPM</th><th>CPC</th><th>CTR</th><th>Conversões</th>
  </tr></thead><tbody>${trs}</tbody></table>`;
}

function renderCampaigns(data) {
  document.getElementById('c-meta').innerHTML = brkTable(data.meta_campaigns, data.meta.currency||'BRL', false, false);
  document.getElementById('c-google').innerHTML = brkTable(data.google_campaigns, data.google_ads.currency||'BRL', false, false);
}
function renderAdsets(data) {
  document.getElementById('as-meta').innerHTML = brkTable(data.meta_adsets, data.meta.currency||'BRL', true, false);
  document.getElementById('as-google').innerHTML = brkTable(data.google_adgroups, data.google_ads.currency||'BRL', true, false);
}
function renderAds(data) {
  document.getElementById('ad-meta').innerHTML = brkTable(data.meta_ads, data.meta.currency||'BRL', true, true);
  document.getElementById('ad-google').innerHTML = brkTable(data.google_ads_breakdown, data.google_ads.currency||'BRL', true, true);
}
function renderGeo(data) {
  document.getElementById('geo-meta').innerHTML = geoTable(data.meta_geo, data.meta.currency||'BRL');
  document.getElementById('geo-google').innerHTML = geoTable(data.google_geo, data.google_ads.currency||'BRL');
}

renderView();

function renderRelatorio(data) {
  const {meta: m, google_ads: g, ga4, woocommerce: wc, meta_campaigns, google_campaigns, meta_adsets, google_adgroups, meta_ads, google_ads_breakdown} = data;
  const mCur = m.currency || 'BRL', gCur = g.currency || 'BRL';
  const ts = m.spend + g.spend, tr = m.revenue + g.revenue;
  const tconv = (m.purchases || 0) + (g.conversions || 0);
  const tc = m.clicks + g.clicks, ti = m.impressions + g.impressions;

  const b = (v, c) => (c==='EUR'?'€ ':'R$ ') + (+v||0).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2});
  const n = v => Math.round(+v||0).toLocaleString('pt-BR');
  const p = v => (+v||0).toFixed(2) + '%';
  const x = v => (+v||0).toFixed(2) + 'x';
  const line = '━'.repeat(40);
  const dash = '—';

  const periodLabel = {ontem:'Ontem',d7:'Últimos 7 dias',d30:'Últimos 30 dias',mtd:'Mês até hoje',last_month:'Mês passado',apr1:'1º de Abril até hoje'}[curPeriod] || curPeriod;

  let r = '';
  r += 'RELATÓRIO DE PERFORMANCE\n';
  r += periodLabel.toUpperCase() + '\n';
  r += line + '\n\n';

  r += 'RESUMO GERAL\n';
  r += `Investimento Total ........ ${b(ts,'BRL')}\n`;
  r += `  Meta Ads ................ ${b(m.spend,mCur)}\n`;
  r += `  Google Ads .............. ${b(g.spend,gCur)}\n`;
  r += `Receita (atribuída) ....... ${b(tr,'BRL')}\n`;
  r += `ROAS Blendado ............. ${x(ts?tr/ts:0)}\n`;
  r += `CPA Blendado .............. ${b(tconv?ts/tconv:0,'BRL')}\n`;
  r += `Conversões Totais ......... ${n(tconv)}\n`;
  r += `Impressões ................ ${n(ti)}\n`;
  r += `Cliques ................... ${n(tc)}\n`;
  r += `CTR Blendado .............. ${p(ti?tc/ti*100:0)}\n`;
  r += `CPM Blendado .............. ${b(ti?ts/ti*1000:0,'BRL')}\n`;
  r += `CPC Blendado .............. ${b(tc?ts/tc:0,'BRL')}\n\n`;

  r += line + '\n';
  r += 'META ADS\n';
  r += line + '\n';
  r += `Investimento .............. ${b(m.spend,mCur)}\n`;
  r += `Impressões ................ ${n(m.impressions)}\n`;
  r += `Cliques ................... ${n(m.clicks)}\n`;
  r += `CTR ....................... ${p(m.ctr)}\n`;
  r += `CPM ....................... ${b(m.cpm,mCur)}\n`;
  r += `CPC ....................... ${b(m.cpc,mCur)}\n`;
  r += `Compras ................... ${n(m.purchases||0)}\n`;
  r += `Receita ................... ${b(m.revenue,mCur)}\n`;
  r += `ROAS ...................... ${x(m.roas)}\n`;
  r += `CPA ....................... ${b(m.cpa,mCur)}\n`;
  r += `Alcance ................... ${n(m.reach||0)}\n\n`;

  if (meta_campaigns && meta_campaigns.length) {
    r += 'Campanhas Meta (top ' + Math.min(meta_campaigns.length,5) + '):\n';
    meta_campaigns.slice(0,5).forEach((c,i) => {
      r += `  ${i+1}. ${c.name}\n`;
      r += `     Investido: ${b(c.spend,mCur)} | ROAS: ${x(c.roas)} | Compras: ${n(c.purchases||0)} | CPA: ${b(c.cpa,mCur)}\n`;
    });
    r += '\n';
  }

  if (meta_adsets && meta_adsets.length) {
    r += 'Conjuntos Meta (top ' + Math.min(meta_adsets.length,5) + '):\n';
    meta_adsets.slice(0,5).forEach((c,i) => {
      r += `  ${i+1}. ${c.name}\n`;
      r += `     Investido: ${b(c.spend,mCur)} | CTR: ${p(c.ctr)} | CPC: ${b(c.cpc,mCur)} | Compras: ${n(c.purchases||0)}\n`;
    });
    r += '\n';
  }

  if (meta_ads && meta_ads.length) {
    r += 'Anúncios Meta (top ' + Math.min(meta_ads.length,5) + '):\n';
    meta_ads.slice(0,5).forEach((c,i) => {
      r += `  ${i+1}. ${c.name}\n`;
      r += `     Campanha: ${c.campaign||dash} | Conjunto: ${c.adset||dash}\n`;
      r += `     Investido: ${b(c.spend,mCur)} | CTR: ${p(c.ctr)} | Compras: ${n(c.purchases||0)} | ROAS: ${x(c.roas)}\n`;
    });
    r += '\n';
  }

  r += line + '\n';
  r += 'GOOGLE ADS\n';
  r += line + '\n';
  r += `Investimento .............. ${b(g.spend,gCur)}\n`;
  r += `Impressões ................ ${n(g.impressions)}\n`;
  r += `Cliques ................... ${n(g.clicks)}\n`;
  r += `CTR ....................... ${p(g.ctr)}\n`;
  r += `CPM ....................... ${b(g.cpm,gCur)}\n`;
  r += `CPC ....................... ${b(g.cpc,gCur)}\n`;
  r += `Conversões ................ ${n(g.conversions||0)}\n`;
  r += `Receita ................... ${b(g.revenue,gCur)}\n`;
  r += `ROAS ...................... ${x(g.roas)}\n`;
  r += `CPA ....................... ${b(g.cpa,gCur)}\n\n`;

  if (google_campaigns && google_campaigns.length) {
    r += 'Campanhas Google (top ' + Math.min(google_campaigns.length,5) + '):\n';
    google_campaigns.slice(0,5).forEach((c,i) => {
      r += `  ${i+1}. ${c.name} [${c.status}]\n`;
      r += `     Investido: ${b(c.spend,gCur)} | ROAS: ${x(c.roas)} | Conv.: ${n(c.conversions||0)} | CPA: ${b(c.cpa,gCur)}\n`;
    });
    r += '\n';
  }

  if (google_adgroups && google_adgroups.length) {
    r += 'Grupos Google (top ' + Math.min(google_adgroups.length,5) + '):\n';
    google_adgroups.slice(0,5).forEach((c,i) => {
      r += `  ${i+1}. ${c.name}\n`;
      r += `     Campanha: ${c.campaign||dash} | Investido: ${b(c.spend,gCur)} | CTR: ${p(c.ctr)} | Conv.: ${n(c.conversions||0)}\n`;
    });
    r += '\n';
  }

  r += line + '\n';
  r += 'GOOGLE ANALYTICS 4\n';
  r += line + '\n';
  r += `Sessões ................... ${n(ga4.sessions)}\n`;
  r += `Usuários .................. ${n(ga4.users)}\n`;
  r += `Transações ................ ${n(ga4.transactions)}\n`;
  r += `Receita GA4 ............... ${b(ga4.revenue,'BRL')}\n`;
  r += `Taxa de Conversão ......... ${p(ga4.conversion_rate)}\n`;
  r += `Custo por Visita .......... ${b(ga4.sessions?ts/ga4.sessions:0,'BRL')}\n`;
  r += `Connect Rate .............. ${p(tc?ga4.sessions/tc*100:0)}\n\n`;

  r += line + '\n';
  r += 'LOJA (WOOCOMMERCE)\n';
  r += line + '\n';
  r += `Pedidos ................... ${n(wc.orders)}\n`;
  r += `Receita ................... ${b(wc.revenue,'BRL')}\n`;
  r += `Ticket Médio .............. ${b(wc.avg_ticket,'BRL')}\n\n`;

  r += line + '\n';
  r += `Gerado em: ${new Date().toLocaleString('pt-BR')}\n`;

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
        "meta_campaigns": fetch_meta_breakdown(since, until, "campaign"),
        "meta_adsets": fetch_meta_breakdown(since, until, "adset"),
        "meta_ads": fetch_meta_breakdown(since, until, "ad"),
        "google_campaigns": fetch_google_campaigns(since, until),
        "google_adgroups": fetch_google_adgroups(since, until),
        "google_ads_breakdown": fetch_google_ads_breakdown(since, until),
        "meta_geo": fetch_meta_geo(since, until),
        "google_geo": fetch_google_geo(since, until),
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

    print("Buscando dados...")
    apr1_start = today.replace(month=4, day=1).strftime("%Y-%m-%d")

    data = {
        "ontem": _fetch_period(yesterday, yesterday),
        "d7": _fetch_period(d7_start, today_str),
        "d30": _fetch_period(d30_start, today_str),
        "mtd": _fetch_period(mtd_start, today_str),
        "last_month": _fetch_period(last_month_start, last_month_end.strftime("%Y-%m-%d")),
        "apr1": _fetch_period(apr1_start, today_str),
    }

    client_name = os.environ.get("CLIENT_NAME", "Dashboard")
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
    print(f"Gerado: index.html ({updated_at})")


if __name__ == "__main__":
    main()
