#!/usr/bin/env python3
import json
import os
import requests
from datetime import datetime, timedelta

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Metric, RunReportRequest
from google.oauth2 import service_account
from woocommerce import API as WcAPI


def fetch_meta(since, until):
    try:
        r = requests.get(
            f"https://graph.facebook.com/v19.0/{os.environ['META_ACCOUNT_ID']}/insights",
            params={
                "access_token": os.environ["META_ACCESS_TOKEN"],
                "fields": "spend,impressions,clicks,reach,actions,action_values,cpc,ctr",
                "time_range": json.dumps({"since": since, "until": until}),
                "level": "account",
            },
            timeout=30,
        )
        raw = r.json().get("data", [])
        d = raw[0] if raw else {}
        spend = float(d.get("spend", 0))
        actions = {a["action_type"]: float(a["value"]) for a in d.get("actions", [])}
        action_vals = {a["action_type"]: float(a["value"]) for a in d.get("action_values", [])}
        purchases = int(actions.get("purchase", 0))
        revenue = action_vals.get("purchase", 0.0)
        return {
            "spend": spend,
            "impressions": int(d.get("impressions", 0)),
            "clicks": int(d.get("clicks", 0)),
            "reach": int(d.get("reach", 0)),
            "cpc": float(d.get("cpc", 0)),
            "ctr": float(d.get("ctr", 0)),
            "purchases": purchases,
            "revenue": revenue,
            "cpa": spend / purchases if purchases else 0,
            "roas": revenue / spend if spend else 0,
        }
    except Exception as e:
        print(f"[Meta Ads] {e}")
        return {"spend": 0, "impressions": 0, "clicks": 0, "reach": 0, "cpc": 0, "ctr": 0, "purchases": 0, "revenue": 0, "cpa": 0, "roas": 0}


def fetch_google_ads(since, until):
    try:
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
            raise RuntimeError(f"token exchange failed: {tok.get('error')}")

        access_token = tok["access_token"]
        customer_id = os.environ["GOOGLE_ADS_CUSTOMER_ID"].replace("-", "").strip()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "developer-token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"].strip(),
            "Content-Type": "application/json",
        }
        login_cid = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "").strip()
        if login_cid:
            headers["login-customer-id"] = login_cid
        query = (
            f"SELECT metrics.cost_micros, metrics.impressions, metrics.clicks,"
            f" metrics.conversions, metrics.conversions_value"
            f" FROM customer"
            f" WHERE segments.date BETWEEN '{since}' AND '{until}'"
        )
        r = requests.post(
            f"https://googleads.googleapis.com/v20/customers/{customer_id}/googleAds:search",
            headers=headers,
            json={"query": query},
            timeout=30,
        )
        data = r.json()
        if "error" in data:
            raise RuntimeError(data["error"].get("message", str(data["error"])))
        cost = imp = clicks = conv = rev = 0.0
        for result in data.get("results", []):
            m = result.get("metrics", {})
            cost += int(m.get("costMicros", 0)) / 1_000_000
            imp += int(m.get("impressions", 0))
            clicks += int(m.get("clicks", 0))
            conv += float(m.get("conversions", 0))
            rev += float(m.get("conversionsValue", 0))
        return {
            "spend": cost,
            "impressions": int(imp),
            "clicks": int(clicks),
            "cpc": cost / clicks if clicks else 0,
            "ctr": clicks / imp * 100 if imp else 0,
            "conversions": int(conv),
            "revenue": rev,
            "cpa": cost / conv if conv else 0,
            "roas": rev / cost if cost else 0,
        }
    except Exception as e:
        print(f"[Google Ads] {e}")
        return {"spend": 0, "impressions": 0, "clicks": 0, "cpc": 0, "ctr": 0, "conversions": 0, "revenue": 0, "cpa": 0, "roas": 0}


def _ga4_via_rest(since, until, access_token):
    prop = os.environ["GA4_PROPERTY_ID"].strip()
    r = requests.post(
        f"https://analyticsdata.googleapis.com/v1beta/properties/{prop}:runReport",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "dateRanges": [{"startDate": since, "endDate": until}],
            "metrics": [
                {"name": "sessions"},
                {"name": "totalUsers"},
                {"name": "transactions"},
                {"name": "purchaseRevenue"},
                {"name": "sessionConversionRate"},
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
    return {
        "sessions": int(v[0]),
        "users": int(v[1]),
        "transactions": int(v[2]),
        "revenue": float(v[3]),
        "conversion_rate": float(v[4]) * 100,
    }


def fetch_ga4(since, until):
    try:
        refresh_token = os.environ.get("GA4_REFRESH_TOKEN", "").strip()
        if refresh_token:
            tok = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "refresh_token": refresh_token,
                    "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"].strip(),
                    "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"].strip(),
                    "grant_type": "refresh_token",
                },
                timeout=15,
            ).json()
            if "access_token" not in tok:
                raise RuntimeError(f"token exchange failed: {tok.get('error')}")
            return _ga4_via_rest(since, until, tok["access_token"])
        else:
            creds = service_account.Credentials.from_service_account_info(
                json.loads(os.environ["GA4_CREDENTIALS_JSON"]),
                scopes=["https://www.googleapis.com/auth/analytics.readonly"],
            )
            client = BetaAnalyticsDataClient(credentials=creds)
            resp = client.run_report(RunReportRequest(
                property=f"properties/{os.environ['GA4_PROPERTY_ID'].strip()}",
                date_ranges=[DateRange(start_date=since, end_date=until)],
                metrics=[
                    Metric(name="sessions"),
                    Metric(name="totalUsers"),
                    Metric(name="transactions"),
                    Metric(name="purchaseRevenue"),
                    Metric(name="sessionConversionRate"),
                ],
            ))
            if not resp.rows:
                return {"sessions": 0, "users": 0, "transactions": 0, "revenue": 0.0, "conversion_rate": 0.0}
            v = [mv.value for mv in resp.rows[0].metric_values]
            return {
                "sessions": int(v[0]),
                "users": int(v[1]),
                "transactions": int(v[2]),
                "revenue": float(v[3]),
                "conversion_rate": float(v[4]) * 100,
            }
    except Exception as e:
        print(f"[GA4] {e}")
        return {"sessions": 0, "users": 0, "transactions": 0, "revenue": 0.0, "conversion_rate": 0.0}


def fetch_woocommerce(since, until):
    try:
        wc = WcAPI(
            url=os.environ["WC_STORE_URL"],
            consumer_key=os.environ["WC_CONSUMER_KEY"],
            consumer_secret=os.environ["WC_CONSUMER_SECRET"],
            version="wc/v3",
            timeout=30,
        )
        orders = wc.get("orders", params={
            "after": since + "T00:00:00",
            "before": until + "T23:59:59",
            "status": "completed,processing",
            "per_page": 100,
        }).json()
        if not isinstance(orders, list):
            return {"orders": 0, "revenue": 0.0, "avg_ticket": 0.0}
        rev = sum(float(o.get("total", 0)) for o in orders)
        n = len(orders)
        return {"orders": n, "revenue": rev, "avg_ticket": rev / n if n else 0}
    except Exception as e:
        print(f"[WooCommerce] {e}")
        return {"orders": 0, "revenue": 0.0, "avg_ticket": 0.0}


HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__CLIENT_NAME__ — Dashboard</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f5f7;color:#1d1d1f}
header{background:#111;color:#fff;padding:20px 32px;display:flex;justify-content:space-between;align-items:center}
header h1{font-size:18px;font-weight:600;letter-spacing:-.01em}
.upd{font-size:12px;color:#777}
main{max-width:1200px;margin:0 auto;padding:28px 32px}
.tabs{display:flex;gap:8px;margin-bottom:28px}
.tab{padding:8px 18px;border-radius:20px;font-size:13px;cursor:pointer;border:none;background:#e5e5ea;color:#1d1d1f;font-weight:500;transition:background .15s,color .15s}
.tab.active{background:#111;color:#fff}
.sec{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#86868b;margin:28px 0 14px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:14px}
.card{background:#fff;border-radius:12px;padding:18px 20px}
.card.blue{background:#0055ff;color:#fff}
.lbl{font-size:11px;color:#86868b;margin-bottom:8px}
.card.blue .lbl{color:rgba(255,255,255,.65)}
.val{font-size:24px;font-weight:700;letter-spacing:-.02em;line-height:1}
.sub{font-size:11px;color:#86868b;margin-top:5px}
.card.blue .sub{color:rgba(255,255,255,.6)}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden}
th{text-align:left;padding:11px 16px;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:#86868b;border-bottom:1px solid #f2f2f7}
td{padding:14px 16px;font-size:13px;border-bottom:1px solid #f2f2f7}
tr.total td{border-bottom:none;font-weight:700;background:#f5f5f7}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:8px;vertical-align:middle}
footer{text-align:center;padding:32px;font-size:12px;color:#aaa}
@media(max-width:640px){main{padding:20px 16px}header{padding:16px}th,td{padding:10px 12px}table{font-size:12px}}
</style>
</head>
<body>
<header>
  <h1>__CLIENT_NAME__</h1>
  <span class="upd">Atualizado __UPDATED_AT__</span>
</header>
<main>
  <div class="tabs">
    <button class="tab active" onclick="render('ontem',this)">Ontem</button>
    <button class="tab" onclick="render('mtd',this)">Mês até hoje</button>
  </div>
  <p class="sec">Investimento e Retorno</p>
  <div class="grid" id="kpi"></div>
  <p class="sec">Por Plataforma</p>
  <table>
    <thead><tr>
      <th>Plataforma</th><th>Investido</th><th>Cliques</th><th>Impressões</th>
      <th>Conversões</th><th>Receita</th><th>CPA</th><th>ROAS</th>
    </tr></thead>
    <tbody id="ptable"></tbody>
  </table>
  <p class="sec">Site — Google Analytics 4</p>
  <div class="grid" id="ga4"></div>
  <p class="sec">Pedidos — Loja</p>
  <div class="grid" id="wc"></div>
</main>
<footer>Dashboard gerado automaticamente · __UPDATED_AT__</footer>
<script>
const D = __DATA_JSON__;
const brl = v => 'R$ ' + (+v||0).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2});
const num = v => Math.round(+v||0).toLocaleString('pt-BR');
const xr  = v => (+v||0).toFixed(2) + 'x';
const pct = v => (+v||0).toFixed(2) + '%';
const card = (l,v,s,blue) => `<div class="card${blue?' blue':''}"><div class="lbl">${l}</div><div class="val">${v}</div>${s?`<div class="sub">${s}</div>`:''}</div>`;
const prow = (color,name,d,conv) => `<tr>
  <td><span class="dot" style="background:${color}"></span>${name}</td>
  <td>${brl(d.spend)}</td><td>${num(d.clicks)}</td><td>${num(d.impressions)}</td>
  <td>${num(conv)}</td><td>${brl(d.revenue)}</td><td>${brl(d.cpa)}</td><td>${xr(d.roas)}</td></tr>`;
function render(p, btn) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  if (btn) btn.classList.add('active');
  const {meta:m, google_ads:g, ga4, woocommerce:wc} = D[p];
  const ts = m.spend + g.spend;
  const tc = m.clicks + g.clicks;
  const ti = m.impressions + g.impressions;
  const tconv = (m.purchases||0) + (g.conversions||0);
  const tr = m.revenue + g.revenue;
  const tcpa = tconv ? ts/tconv : 0;
  const troas = ts ? tr/ts : 0;
  document.getElementById('kpi').innerHTML = [
    card('Total Investido', brl(ts), 'Meta + Google Ads', true),
    card('Receita (Ads)', brl(tr), 'atribuição das plataformas'),
    card('ROAS Blendado', xr(troas), 'retorno sobre investimento'),
    card('CPA Blendado', brl(tcpa), 'custo por conversão'),
    card('Conversões', num(tconv), 'compras atribuídas'),
    card('Cliques Totais', num(tc), 'Meta + Google Ads'),
  ].join('');
  document.getElementById('ptable').innerHTML =
    prow('#0866ff','Meta Ads', m, m.purchases||0) +
    prow('#ea4335','Google Ads', g, g.conversions||0) +
    `<tr class="total"><td>Total</td><td>${brl(ts)}</td><td>${num(tc)}</td><td>${num(ti)}</td><td>${num(tconv)}</td><td>${brl(tr)}</td><td>${brl(tcpa)}</td><td>${xr(troas)}</td></tr>`;
  document.getElementById('ga4').innerHTML = [
    card('Sessões', num(ga4.sessions), ''),
    card('Usuários', num(ga4.users), ''),
    card('Transações', num(ga4.transactions), ''),
    card('Receita GA4', brl(ga4.revenue), ''),
    card('Taxa de Conversão', pct(ga4.conversion_rate), ''),
  ].join('');
  document.getElementById('wc').innerHTML = [
    card('Pedidos', num(wc.orders), ''),
    card('Receita Loja', brl(wc.revenue), ''),
    card('Ticket Médio', brl(wc.avg_ticket), ''),
  ].join('');
}
render('ontem');
</script>
</body>
</html>""";


def main():
    today = datetime.now()
    yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    mtd_start = today.replace(day=1).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")

    print("Buscando dados...")
    data = {
        "ontem": {
            "meta": fetch_meta(yesterday, yesterday),
            "google_ads": fetch_google_ads(yesterday, yesterday),
            "ga4": fetch_ga4(yesterday, yesterday),
            "woocommerce": fetch_woocommerce(yesterday, yesterday),
        },
        "mtd": {
            "meta": fetch_meta(mtd_start, today_str),
            "google_ads": fetch_google_ads(mtd_start, today_str),
            "ga4": fetch_ga4(mtd_start, today_str),
            "woocommerce": fetch_woocommerce(mtd_start, today_str),
        },
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
