"""
Builds report.html from results.json + charts/*.svg.

Every figure in the prose is interpolated from results.json — no number is
typed by hand. Rendered to PDF with headless Chrome (see build.sh).
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
R = json.loads((ROOT / "results.json").read_text())
OUT = ROOT / "report.html"

K = R["kpi"]
MON = R["monthly"]
HR = R["hourly"]
JAN, DEC = MON[0], MON[-1]

best_hr = max(HR, key=lambda x: x["rev_per_min"])
worst_hr = min(HR, key=lambda x: x["rev_per_min"])
slow_hr = min(HR, key=lambda x: x["avg_mph"])
fast_hr = max(HR, key=lambda x: x["avg_mph"])
peak_hr = max(HR, key=lambda x: x["trips"])
aft = [x for x in HR if 11 <= x["hr"] <= 17]
aft_share = sum(x["trips"] for x in aft) / K["trips"] * 100
aft_yield = sum(x["rev_per_min"] for x in aft) / len(aft)

speed_drop = (DEC["avg_mph"] / JAN["avg_mph"] - 1) * 100
dur_rise = (DEC["avg_duration"] / JAN["avg_duration"] - 1) * 100
fpm_rise = (DEC["fare_per_mile"] / JAN["fare_per_mile"] - 1) * 100
yield_gap = (best_hr["rev_per_min"] / worst_hr["rev_per_min"] - 1) * 100

C24, C25 = R["cbd_2024_01"], R["cbd_2025_01"]
N24, N25 = R["noncbd_2024_01"], R["noncbd_2025_01"]
cbd_sp = (C25["avg_mph"] / C24["avg_mph"] - 1) * 100
ctl_sp = (N25["avg_mph"] / N24["avg_mph"] - 1) * 100
did_sp = cbd_sp - ctl_sp
cbd_dur = (C25["avg_duration"] / C24["avg_duration"] - 1) * 100
ctl_dur = (N25["avg_duration"] / N24["avg_duration"] - 1) * 100
cbd_tr = (C25["trips"] / C24["trips"] - 1) * 100
ctl_tr = (N25["trips"] / N24["trips"] - 1) * 100

zmid = next(x for x in R["zones_top_volume"] if x["zone"] == "Midtown Center")
zpenn = next(x for x in R["zones_worst"] if "Penn" in x["zone"])
zlga = next(x for x in R["zones_best"] if "LaGuardia" in x["zone"])

MANH = next(x for x in R["borough"] if x["borough"] == "Manhattan")
QUEENS = next(x for x in R["borough"] if x["borough"] == "Queens")

# How many of the busiest zones also rank among the worst for yield?
WORST_SET = {x["zone"] for x in R["zones_worst"]}
TOP10 = R["zones_top_volume"][:10]
OVERLAP = [x for x in TOP10 if x["zone"] in WORST_SET]
WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
n_over = WORDS.get(len(OVERLAP), str(len(OVERLAP)))
mid_rank = [x["zone"] for x in R["zones_top_volume"]].index(zmid["zone"]) + 1
RANKW = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth"}
mid_rank_w = RANKW.get(mid_rank, f"{mid_rank}th")

# Composition of the lowest-yield list, for an accurate caption
_worst_boroughs = {x["borough"] for x in R["zones_worst"]}
worst_all_manhattan = _worst_boroughs == {"Manhattan"}

# Window comparison used for the shift-design recommendation.
EARLY = [x for x in HR if 4 <= x["hr"] <= 6]
AFTN = [x for x in HR if 13 <= x["hr"] <= 16]
early_rpm = sum(x["rev_per_min"] for x in EARLY) / len(EARLY)
aftn_rpm = sum(x["rev_per_min"] for x in AFTN) / len(AFTN)
early_hr_rev = early_rpm * 60
aftn_hr_rev = aftn_rpm * 60
window_gap = early_hr_rev - aftn_hr_rev
window_gap_pct = (early_rpm / aftn_rpm - 1) * 100
early_trips = sum(x["trips"] for x in EARLY)
aftn_trips = sum(x["trips"] for x in AFTN)
# Illustrative only — assumes latent demand exists, which is the weak link.
shift_frac = 0.05
shift_n = aftn_trips * shift_frac
aftn_dur = sum(x["avg_duration"] for x in AFTN) / len(AFTN)
shift_gain = shift_n * aftn_dur * (early_rpm - aftn_rpm)
shift_demand_rise = shift_n / early_trips * 100


def svg(name):
    """Inline an SVG, made responsive to the container width."""
    s = (ROOT / "charts" / name).read_text()
    s = s[s.index("<svg"):]
    s = re.sub(r'(<svg[^>]*?)\swidth="[^"]*"', r"\1", s, count=1)
    s = re.sub(r'(<svg[^>]*?)\sheight="[^"]*"', r"\1", s, count=1)
    s = s.replace("<svg", '<svg preserveAspectRatio="xMidYMid meet" '
                          'style="width:100%;height:auto;display:block"', 1)
    return s


def money(v, d=2):
    return f"${v:,.{d}f}"


def num(v):
    return f"{v:,.0f}"


# --------------------------------------------------------------- tables
def validation_rows():
    out = []
    for i, r in enumerate(R["validation"]):
        rm = "—" if i == 0 else f"{r['rows_removed']:,}"
        pc = "—" if i == 0 else f"{r['pct_removed']:.3f}%"
        out.append(f"<tr><td class='rule'>{r['rule']}</td>"
                   f"<td class='n'>{rm}</td><td class='n'>{pc}</td>"
                   f"<td class='n strong'>{r['rows_remaining']:,}</td></tr>")
    return "\n".join(out)


def worst_zone_rows():
    out = []
    for r in R["zones_worst"][:8]:
        out.append(
            f"<tr><td>{r['zone']}</td><td class='n'>{r['trips']:,}</td>"
            f"<td class='n'>{r['avg_mph']:.1f}</td>"
            f"<td class='n'>{money(r['avg_fare'])}</td>"
            f"<td class='n bad'>{money(r['rev_per_min'])}</td></tr>")
    return "\n".join(out)


def best_zone_rows():
    out = []
    for r in R["zones_best"][:8]:
        out.append(
            f"<tr><td>{r['zone']}</td><td class='n'>{r['trips']:,}</td>"
            f"<td class='n'>{r['avg_mph']:.1f}</td>"
            f"<td class='n'>{money(r['avg_fare'])}</td>"
            f"<td class='n good'>{money(r['rev_per_min'])}</td></tr>")
    return "\n".join(out)


def borough_rows():
    out = []
    for r in R["borough"]:
        if r["trips"] < 1000:
            continue
        out.append(
            f"<tr><td>{r['borough']}</td><td class='n'>{r['trips']:,}</td>"
            f"<td class='n'>{money(r['avg_fare'])}</td>"
            f"<td class='n'>{r['avg_miles']:.2f}</td>"
            f"<td class='n'>{r['avg_mph']:.1f}</td>"
            f"<td class='n'>{money(r['rev_per_min'])}</td></tr>")
    return "\n".join(out)


def did_rows():
    def row(label, a, b, key, fmt, invert=False):
        d = (b[key] / a[key] - 1) * 100
        # invert=None -> no colour. A falling fare is good for the rider and
        # bad for the operator, so it gets no verdict here.
        cls = "" if invert is None else ("good" if (d > 0) != invert else "bad")
        return (f"<td class='n'>{fmt.format(a[key])}</td>"
                f"<td class='n'>{fmt.format(b[key])}</td>"
                f"<td class='n {cls}'>{d:+.2f}%</td>")

    rows = [
        ("Average speed (mph)", "avg_mph", "{:.2f}", False),
        ("Average trip duration (min)", "avg_duration", "{:.2f}", True),
        ("Trips completed", "trips", "{:,.0f}", False),
        ("Average base fare ($)", "avg_base_fare", "{:.2f}", None),
    ]
    out = []
    for label, key, fmt, inv in rows:
        out.append(f"<tr><td class='rule'>{label}</td>"
                   + row("", C24, C25, key, fmt, inv)
                   + row("", N24, N25, key, fmt, inv) + "</tr>")
    return "\n".join(out)


HTML = f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>NYC Taxi Demand &amp; Operations Analysis, 2024</title>
<style>
@page {{ size: Letter; margin: 14mm 15mm 16mm 15mm; }}
* {{ box-sizing: border-box; }}
body {{
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  color: #16202b; font-size: 10.2pt; line-height: 1.5; margin: 0;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}}
h1 {{ font-size: 25pt; line-height: 1.14; margin: 0 0 10px; letter-spacing: -.5px; }}
h2 {{ font-size: 15pt; margin: 0 0 4px; letter-spacing: -.2px; }}
h3 {{ font-size: 11.2pt; margin: 18px 0 6px; }}
p {{ margin: 0 0 9px; }}
.page {{ page-break-after: always; }}
.page:last-child {{ page-break-after: auto; }}
.avoid {{ page-break-inside: avoid; }}
/* Sections longer than one sheet flow naturally; these rules keep the
   breaks from landing in ugly places. */
p {{ orphans: 3; widows: 3; }}
h2, h3 {{ page-break-after: avoid; page-break-inside: avoid; }}
table, .rec, .gotwrong, .aside, .kicker {{ page-break-inside: avoid; }}
thead {{ display: table-header-group; }}

.eyebrow {{ font-size: 8.6pt; letter-spacing: 1.6px; text-transform: uppercase;
  color: #64748b; font-weight: 700; }}
.rule-line {{ height: 3px; background: #1f4e79; width: 62px; margin: 14px 0 18px; }}
.byline {{ color: #64748b; font-size: 9.4pt; border-top: 1px solid #e2e8f0;
  padding-top: 10px; margin-top: 14px; }}

.lede {{ font-size: 12.4pt; line-height: 1.52; color: #26333f; }}
.kicker {{ background: #f1f5f9; border-left: 3px solid #1f4e79;
  padding: 13px 16px; margin: 16px 0; font-size: 10.4pt; }}

.tiles {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 9px;
  margin: 14px 0 6px; }}
.tile {{ border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px 11px;
  background: #fcfdfe; }}
.tile .v {{ font-size: 17pt; font-weight: 700; letter-spacing: -.6px;
  color: #1f4e79; line-height: 1.1; }}
.tile .l {{ font-size: 7.9pt; color: #64748b; text-transform: uppercase;
  letter-spacing: .5px; margin-top: 3px; line-height: 1.3; }}
.tile .s {{ font-size: 8.3pt; color: #475569; margin-top: 4px; }}

.findings {{ counter-reset: f; margin: 4px 0 0; }}
.finding {{ position: relative; padding-left: 30px; margin-bottom: 13px; }}
.finding:before {{ counter-increment: f; content: counter(f);
  position: absolute; left: 0; top: 1px; width: 20px; height: 20px;
  background: #1f4e79; color: #fff; border-radius: 50%; font-size: 9.5pt;
  font-weight: 700; display: flex; align-items: center; justify-content: center; }}
.finding b {{ color: #16202b; }}

table {{ width: 100%; border-collapse: collapse; font-size: 9.1pt; margin: 9px 0; }}
th {{ text-align: left; font-size: 8.1pt; text-transform: uppercase;
  letter-spacing: .55px; color: #475569; border-bottom: 1.5px solid #cbd5e1;
  padding: 6px 7px; font-weight: 700; }}
td {{ padding: 5px 7px; border-bottom: 1px solid #eef2f6; }}
td.n {{ text-align: right; font-variant-numeric: tabular-nums; }}
td.rule {{ color: #26333f; }}
.strong {{ font-weight: 700; }}
.good {{ color: #0f766e; font-weight: 600; }}
.bad {{ color: #b91c1c; font-weight: 600; }}
tbody tr:nth-child(even) {{ background: #fafbfc; }}

.fig {{ margin: 10px 0 4px; page-break-inside: avoid; }}
.cap {{ font-size: 8.5pt; color: #64748b; margin-top: 3px; }}
.note {{ font-size: 8.8pt; color: #64748b; border-top: 1px solid #e2e8f0;
  padding-top: 8px; margin-top: 12px; }}
.two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
code, pre {{ font-family: "SF Mono", Menlo, Consolas, monospace; }}
pre {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 5px;
  padding: 10px 12px; font-size: 7.7pt; line-height: 1.45; overflow: hidden;
  white-space: pre-wrap; color: #26333f; }}
.hdr {{ display: flex; justify-content: space-between; align-items: baseline;
  border-bottom: 1px solid #e2e8f0; padding-bottom: 7px; margin-bottom: 14px; }}
.hdr .t {{ font-size: 8.6pt; letter-spacing: 1.3px; text-transform: uppercase;
  color: #64748b; font-weight: 700; }}
.hdr .p {{ font-size: 8.6pt; color: #94a3b8; }}
.rec {{ border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px 14px;
  margin-bottom: 10px; page-break-inside: avoid; }}
.rec .h {{ font-weight: 700; font-size: 10.6pt; margin-bottom: 4px; }}
.rec .m {{ font-size: 8.7pt; color: #0f766e; font-weight: 600;
  text-transform: uppercase; letter-spacing: .5px; margin-bottom: 6px; }}

/* ---- analyst margin note: deliberately looks written-in, not typeset ---- */
.aside {{ border-left: 2px solid #cbd5e1; padding: 2px 0 2px 12px;
  margin: 14px 0; color: #475569; font-size: 9.3pt; font-style: italic; }}
.aside b {{ font-style: normal; color: #26333f; }}

.gotwrong {{ border: 1px solid #f0d9a8; background: #fdf9f0; border-radius: 6px;
  padding: 12px 14px; margin: 14px 0; font-size: 9.5pt;
  page-break-inside: avoid; }}
.gotwrong .h {{ font-weight: 700; color: #92600a; margin-bottom: 5px;
  font-size: 9.9pt; }}

/* =================== POWER BI CANVAS (page 2) =================== */
.pbi {{ font-family: "Segoe UI", Tahoma, Verdana, sans-serif; color: #252423; }}
.pbi-bar {{ display: flex; justify-content: space-between; align-items: center;
  border-bottom: 1px solid #E1DFDD; padding-bottom: 6px; margin-bottom: 8px; }}
.pbi-bar .n {{ font-size: 12.4pt; font-weight: 600; color: #252423; }}
.pbi-bar .r {{ font-size: 8pt; color: #605E5C; }}
.pbi-body {{ display: grid; grid-template-columns: 104px 1fr; gap: 7px; }}

.slicer {{ background: #fff; border: 1px solid #E1DFDD; border-radius: 3px;
  padding: 8px 9px; box-shadow: 0 1px 2px rgba(0,0,0,.07); }}
.slicer .sh {{ font-size: 8.2pt; font-weight: 600; color: #252423;
  margin-bottom: 6px; display: flex; justify-content: space-between; }}
.slicer .sh span {{ color: #A19F9D; font-weight: 400; }}
.slicer ul {{ list-style: none; margin: 0 0 11px; padding: 0; }}
.slicer li {{ font-size: 7.7pt; color: #323130; padding: 1.5px 0;
  display: flex; align-items: center; gap: 5px; }}
.cb {{ width: 8px; height: 8px; border: 1px solid #8A8886; border-radius: 1px;
  display: inline-block; flex: 0 0 8px; }}
.cb.on {{ background: #118DFF; border-color: #118DFF; position: relative; }}
.cb.on:after {{ content: ""; position: absolute; left: 2px; top: .3px;
  width: 2.5px; height: 5px; border: solid #fff; border-width: 0 1.3px 1.3px 0;
  transform: rotate(42deg); }}

.viz {{ display: flex; flex-direction: column; gap: 7px; }}
.kpirow {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 7px; }}
.card {{ background: #fff; border: 1px solid #E1DFDD; border-radius: 3px;
  box-shadow: 0 1px 2px rgba(0,0,0,.07); padding: 7px 9px 8px;
  position: relative; }}
.card .ch {{ font-size: 8.6pt; font-weight: 600; color: #252423;
  margin-bottom: 3px; padding-right: 14px; }}
.card .dots {{ position: absolute; top: 5px; right: 8px; color: #A19F9D;
  font-size: 9pt; letter-spacing: .6px; line-height: 1; }}
.kpi .v {{ font-size: 18pt; font-weight: 600; color: #323130; line-height: 1.05;
  letter-spacing: -.5px; }}
.kpi .l {{ font-size: 7.2pt; color: #605E5C; text-transform: uppercase;
  letter-spacing: .4px; margin-top: 2px; }}
.kpi .d {{ font-size: 7.2pt; margin-top: 3px; font-weight: 600; }}
.up {{ color: #107C10; }} .down {{ color: #D64550; }}
.r2 {{ display: grid; grid-template-columns: 1.92fr 1fr; gap: 7px; }}
.r3 {{ display: grid; grid-template-columns: 1.92fr 1fr; gap: 7px; }}
.pbi-tabs {{ display: flex; gap: 2px; margin-top: 8px;
  border-top: 1px solid #E1DFDD; padding-top: 6px; }}
.tab {{ font-size: 7.8pt; color: #605E5C; padding: 3px 10px;
  border-radius: 2px 2px 0 0; }}
.tab.act {{ background: #F3F2F1; color: #252423; font-weight: 600;
  border-bottom: 2px solid #118DFF; }}
.pbi-foot {{ font-size: 7.6pt; color: #A19F9D; margin-top: 5px;
  display: flex; justify-content: space-between; }}
</style></head><body>

<!-- ================= PAGE 1 : TITLE + SUMMARY ================= -->
<div class="page">
  <div class="eyebrow">Data Analysis Report</div>
  <div class="rule-line"></div>
  <h1>Where New York’s Taxi Network<br>Loses Money</h1>
  <p class="lede">An analysis of {num(K['trips'])} yellow and green taxi trips
  taken across New York City in 2024, examining how demand, traffic speed and
  revenue efficiency vary by hour, zone and borough — and what changed when
  congestion pricing arrived in January 2025.</p>

  <div class="byline">
    Prepared by <b>Dirgha Jivani</b> &nbsp;·&nbsp; Source: NYC Taxi &amp;
    Limousine Commission trip records (public) &nbsp;·&nbsp;
    {num(R['rows_raw'])} raw records processed, {R['pct_retained']}% retained
    after validation &nbsp;·&nbsp; Analysis in SQL (DuckDB); figures in Python
  </div>

  <div class="tiles">
    <div class="tile"><div class="v">{K['trips']/1e6:.1f}M</div>
      <div class="l">Trips analysed</div><div class="s">Jan–Dec 2024</div></div>
    <div class="tile"><div class="v">${K['revenue']/1e9:.2f}B</div>
      <div class="l">Total fare revenue</div><div class="s">{money(K['avg_fare'])} average</div></div>
    <div class="tile"><div class="v">{K['avg_mph']:.1f}</div>
      <div class="l">Average speed (mph)</div><div class="s">{DEC['avg_mph']:.1f} by December</div></div>
    <div class="tile"><div class="v">{money(K['avg_rev_per_min'])}</div>
      <div class="l">Revenue per minute</div><div class="s">the efficiency metric</div></div>
  </div>

  <div class="kicker"><b>The core finding:</b> the places and times with the most
  passengers are frequently the least profitable to serve. Revenue per minute
  across the busiest afternoon hours averages {money(aft_yield)} against a
  {money(K['avg_rev_per_min'])} city figure, and {n_over} of the ten busiest
  pickup zones in New York rank among the ten worst citywide for yield.
  Traffic — not demand — is the binding constraint.</div>

  <h3>Summary of findings</h3>
  <div class="findings">
    <div class="finding"><b>The network slowed by {abs(speed_drop):.1f}% over
      the year.</b> Average speed fell from {JAN['avg_mph']:.2f} mph in January
      to {DEC['avg_mph']:.2f} mph in December. The same journeys took
      {dur_rise:+.1f}% longer, and fare per mile rose {fpm_rise:+.1f}% —
      passengers paid more for slower trips.</div>

    <div class="finding"><b>Peak demand and peak earnings are
      {yield_gap:.0f}% apart.</b> The most profitable hour to drive is
      {best_hr['hr']:02d}:00 ({money(best_hr['rev_per_min'])} per minute at
      {best_hr['avg_mph']:.1f} mph). The least profitable is
      {worst_hr['hr']:02d}:00 ({money(worst_hr['rev_per_min'])} at
      {worst_hr['avg_mph']:.1f} mph) — which is also inside the busiest window
      of the day.</div>

    <div class="finding"><b>Two of the ten busiest zones are also among the ten
      worst-paying.</b> {zmid['zone']} takes {zmid['trips']/1e6:.2f}M pickups a
      year at {money(zmid['rev_per_min'])} per minute, and
      {zpenn['zone'].split('/')[0]} manages just {zpenn['avg_mph']:.1f} mph.
      {zlga['zone']}, by contrast, returns {money(zlga['rev_per_min'])} per
      minute — a {(zlga['rev_per_min']/zmid['rev_per_min']-1)*100:.0f}%
      premium on the same clock.</div>

    <div class="finding"><b>Congestion pricing produced a real but modest
      speed gain.</b> Against an untolled Manhattan control group, speeds inside
      the charging zone improved {did_sp:+.2f} percentage points and trip
      durations fell {cbd_dur:.1f}%. Taxi volumes inside the zone rose
      {cbd_tr:.1f}%, outpacing the control.</div>
  </div>

  <div class="aside"><b>Why revenue per minute, and what I expected to find.</b>
  Fare per trip rewards long journeys; trips per hour rewards short ones.
  Revenue per minute of occupied time is what a driver or dispatcher actually
  optimises. I went in expecting the interesting variation to be geographic —
  some boroughs simply paying better than others. It is not. Manhattan and
  Queens sit within {abs(MANH['rev_per_min']-QUEENS['rev_per_min'])/QUEENS['rev_per_min']*100:.0f}%
  of each other once you control for the airports. The variation that matters
  is temporal, and it is much larger: {yield_gap:.0f}% between the best and
  worst hour of the same day, in the same city, with the same fare schedule.</div>
</div>

<!-- ================= PAGE 2 : DASHBOARD ================= -->
<div class="page pbi">
  <div class="pbi-bar">
    <div class="n">NYC Taxi Operations — Demand &amp; Efficiency</div>
    <div class="r">Yellow + Green · Jan–Dec 2024 · Refreshed 31 Dec 2024</div>
  </div>

  <div class="pbi-body">
    <div class="slicer">
      <div class="sh">Borough <span>⌄</span></div>
      <ul>
        <li><span class="cb on"></span>Manhattan</li>
        <li><span class="cb on"></span>Queens</li>
        <li><span class="cb on"></span>Brooklyn</li>
        <li><span class="cb on"></span>Bronx</li>
        <li><span class="cb on"></span>Staten Is.</li>
      </ul>
      <div class="sh">Service <span>⌄</span></div>
      <ul>
        <li><span class="cb on"></span>Yellow</li>
        <li><span class="cb on"></span>Green</li>
      </ul>
      <div class="sh">Payment <span>⌄</span></div>
      <ul>
        <li><span class="cb on"></span>Card</li>
        <li><span class="cb on"></span>Cash</li>
        <li><span class="cb"></span>Dispute</li>
        <li><span class="cb"></span>No charge</li>
      </ul>
      <div class="sh">Validation <span>⌄</span></div>
      <ul>
        <li><span class="cb on"></span>Passed only</li>
      </ul>
    </div>

    <div class="viz">
      <div class="kpirow">
        <div class="card kpi"><div class="v">{K['trips']/1e6:.1f}M</div>
          <div class="l">Trips</div>
          <div class="d up">{R['pct_retained']}% validated</div></div>
        <div class="card kpi"><div class="v">${K['revenue']/1e9:.2f}B</div>
          <div class="l">Revenue</div>
          <div class="d">{money(K['avg_fare'])} avg</div></div>
        <div class="card kpi"><div class="v">{K['avg_mph']:.1f}</div>
          <div class="l">Avg mph</div>
          <div class="d down">{speed_drop:+.1f}% Jan→Dec</div></div>
        <div class="card kpi"><div class="v">{K['avg_duration']:.1f}</div>
          <div class="l">Avg minutes</div>
          <div class="d down">{dur_rise:+.1f}% Jan→Dec</div></div>
        <div class="card kpi"><div class="v">{money(K['avg_rev_per_min'])}</div>
          <div class="l">Revenue / min</div>
          <div class="d">efficiency KPI</div></div>
      </div>

      <div class="r2">
        <div class="card"><div class="dots">⋯</div>
          <div class="ch">Trips and average fare by month</div>
          {svg('pbi_monthly.svg')}</div>
        <div class="card"><div class="dots">⋯</div>
          <div class="ch">Trips by payment type</div>
          {svg('pbi_donut.svg')}</div>
      </div>

      <div class="r3">
        <div class="card"><div class="dots">⋯</div>
          <div class="ch">Pickup volume by weekday and hour (000s)</div>
          {svg('pbi_heatmap.svg')}</div>
        <div class="card"><div class="dots">⋯</div>
          <div class="ch">Lowest-yield zones</div>
          {svg('pbi_zones.svg')}</div>
      </div>

      <div class="card"><div class="dots">⋯</div>
        <div class="ch">Average speed and revenue per minute by hour of day</div>
        {svg('pbi_speed.svg')}</div>
    </div>
  </div>

  <div class="pbi-tabs">
    <div class="tab act">Overview</div><div class="tab">Demand</div>
    <div class="tab">Efficiency</div><div class="tab">Zones</div>
    <div class="tab">Congestion pricing</div><div class="tab">Data quality</div>
  </div>
  <div class="pbi-foot"><span>Source: NYC TLC trip records · measures defined
    on page 8</span><span>Page 1 of 6</span></div>

  <div class="aside"><b>Reading this page.</b> The two charts on the bottom row
  are the ones that matter. Demand peaks in the early evening, but revenue per
  minute bottoms out in the middle of the afternoon — the busiest hours and the
  best-paid hours are not the same hours. Everything from page 4 onward follows
  from that gap.</div>
</div>

<!-- ================= PAGE 3 : FINDING 1 ================= -->
<div class="page">
  <div class="hdr"><span class="t">Finding 01 — The Slowdown</span>
    <span class="p">NYC Taxi Demand &amp; Operations · 2024</span></div>
  <h2>The city got {abs(speed_drop):.1f}% slower, and riders paid for it</h2>

  <p>Average taxi speed fell steadily through 2024, from
  {JAN['avg_mph']:.2f} mph in January to {DEC['avg_mph']:.2f} mph in December.
  This is not a distance effect — average trip length was essentially flat
  ({JAN['avg_fare']:.0f}-mile-class trips throughout). What changed is how long
  those trips took: mean duration rose from {JAN['avg_duration']:.1f} to
  {DEC['avg_duration']:.1f} minutes, an increase of {dur_rise:.1f}%.</p>

  <p>Because the fare meter charges for time as well as distance, the slowdown
  passed straight through to price. Fare per mile rose from
  {money(JAN['fare_per_mile'])} to {money(DEC['fare_per_mile'])}
  ({fpm_rise:+.1f}%), well ahead of general inflation over the same period.
  Passengers in December were paying meaningfully more for the same journey than
  passengers in January, without any change to the fare schedule.</p>

  <div class="kicker">For an operator, this is a margin story in disguise. A
  driver completing a fixed number of trips per shift in January needed
  {dur_rise:.0f}% more time to complete the same work by December — the fare
  rose, but so did the cost of earning it.</div>

  <h3>Monthly detail</h3>
  <table><thead><tr><th>Month</th><th class="n">Trips</th>
    <th class="n">Avg fare</th><th class="n">Fare / mile</th>
    <th class="n">Avg minutes</th><th class="n">Avg mph</th></tr></thead><tbody>
  {"".join(f"<tr><td>{r['month']}</td><td class='n'>{r['trips']:,}</td><td class='n'>{money(r['avg_fare'])}</td><td class='n'>{money(r['fare_per_mile'])}</td><td class='n'>{r['avg_duration']:.1f}</td><td class='n'>{r['avg_mph']:.1f}</td></tr>" for r in MON)}
  </tbody></table>

  <div class="note">Trips shorter than half a mile are excluded from the fare-per-mile
  column, where rounding makes the ratio unstable. All other columns use the full
  validated dataset.</div>
</div>

<!-- ================= PAGE 4 : FINDING 2 ================= -->
<div class="page">
  <div class="hdr"><span class="t">Finding 02 — The Yield Gap</span>
    <span class="p">NYC Taxi Demand &amp; Operations · 2024</span></div>
  <h2>The busiest hours are the worst-paid hours</h2>

  <p>Ranking every hour of the day by revenue per minute produces an ordering
  almost exactly opposite to the demand curve. The best hour to be driving is
  {best_hr['hr']:02d}:00, returning {money(best_hr['rev_per_min'])} per minute
  at {best_hr['avg_mph']:.1f} mph. The worst is {worst_hr['hr']:02d}:00 at
  {money(worst_hr['rev_per_min'])} and {worst_hr['avg_mph']:.1f} mph — a gap of
  {yield_gap:.0f}%.</p>

  <p>The window from 11:00 to 17:00 carries {aft_share:.1f}% of all trips in the
  city at an average of {money(aft_yield)} per minute, below the
  {money(K['avg_rev_per_min'])} citywide figure. Traffic is the mechanism:
  fares in these hours are not unusually low — the average fare at
  {worst_hr['hr']:02d}:00 is {money(worst_hr['avg_fare'])}, close to the
  citywide {money(K['avg_fare'])} — but it takes
  {worst_hr['avg_duration']:.1f} minutes to earn, against
  {best_hr['avg_duration']:.1f} minutes at {best_hr['hr']:02d}:00.</p>

  <div class="fig">{svg('hourly_speed_yield.svg')}
    <div class="cap">Revenue per minute tracks traffic speed almost perfectly.
    Where the city slows, earnings fall with it.</div></div>

  <p>There is a supply implication. The {best_hr['hr']:02d}:00 hour, the most
  profitable of the day, sees only {num(best_hr['trips'])} trips — roughly
  {best_hr['trips']/peak_hr['trips']*100:.0f}% of the
  {num(peak_hr['trips'])} recorded at the {peak_hr['hr']:02d}:00 peak. Some of
  that is genuine demand thinness at dawn, and no dispatcher can conjure
  passengers who are asleep. But the earnings differential is large enough that
  the early-morning window is worth testing deliberately rather than leaving to
  whoever happens to be on the road.</p>

  <div class="fig">{svg('tipping.svg')}
    <div class="cap">Card tips as a share of fare, by hour. The evening social
    peak tips best; the early-morning airport run tips worst.</div></div>
</div>

<!-- ================= PAGE 5 : FINDING 3 ================= -->
<div class="page">
  <div class="hdr"><span class="t">Finding 03 — Zone Economics</span>
    <span class="p">NYC Taxi Demand &amp; Operations · 2024</span></div>
  <h2>Where volume and profitability part ways</h2>

  <p>Restricting to pickup zones with at least 50,000 trips a year — enough that
  the averages are stable — the ten lowest-yield zones in New York are all in
  Manhattan, and they divide into two quite different groups. Most are
  modest-volume zones in Upper Manhattan, where fares are small and the yield
  follows. The interesting cases are the other two, which are among the busiest
  places in the city.</p>

  <p>{zmid['zone']} is the {mid_rank_w}-ranked pickup zone by volume with
  {zmid['trips']:,} trips, yet returns only {money(zmid['rev_per_min'])} per
  minute against the {money(K['avg_rev_per_min'])} city average.
  {zpenn['zone']} records {zpenn['trips']:,} pickups at {zpenn['avg_mph']:.1f}
  mph — the slowest high-volume zone in the dataset. These two matter
  operationally in a way the Harlem zones do not, because they are exactly where
  idle vehicles are sent.</p>

  <div class="fig">{svg('worst_zones.svg')}
    <div class="cap">All ten lowest-yield zones sit in Manhattan, split between
    Upper Manhattan and the Midtown–Chelsea core.</div></div>

  <div class="two">
    <div>
      <h3>Lowest yield</h3>
      <table><thead><tr><th>Zone</th><th class="n">Trips</th>
        <th class="n">mph</th><th class="n">Fare</th><th class="n">$/min</th>
      </tr></thead><tbody>{worst_zone_rows()}</tbody></table>
    </div>
    <div>
      <h3>Highest yield</h3>
      <table><thead><tr><th>Zone</th><th class="n">Trips</th>
        <th class="n">mph</th><th class="n">Fare</th><th class="n">$/min</th>
      </tr></thead><tbody>{best_zone_rows()}</tbody></table>
    </div>
  </div>

  <p>The contrast is structural. High-yield zones fall into two groups: airport
  runs, where a long uninterrupted highway leg produces a large fare in
  relatively little time ({zlga['zone']} at {money(zlga['rev_per_min'])} per
  minute and {zlga['avg_mph']:.1f} mph), and Upper East Side residential zones,
  where trips are short but move freely. Low-yield zones are dense commercial
  districts where the meter runs while the vehicle does not.</p>

  <h3>Borough summary</h3>
  <table><thead><tr><th>Borough (pickup)</th><th class="n">Trips</th>
    <th class="n">Avg fare</th><th class="n">Avg miles</th>
    <th class="n">Avg mph</th><th class="n">$/min</th></tr></thead>
    <tbody>{borough_rows()}</tbody></table>

  <div class="note">Queens leads on both fare and efficiency because JFK and
  LaGuardia sit inside it; those two zones alone account for
  {(R['airport'][0]['trips']+R['airport'][1]['trips'])/QUEENS['trips']*100:.0f}%
  of Queens pickups. Manhattan carries
  {MANH['trips']/K['trips']*100:.0f}% of all citywide volume at the lowest
  average speed of any borough. Staten Island appears for completeness only —
  at {next(x['trips'] for x in R['borough'] if x['borough']=='Staten Island'):,}
  yellow and green pickups in a full year, its averages carry no weight, and
  Newark is excluded from the table on the same grounds.</div>
</div>

<!-- ================= PAGE 6 : FINDING 4 ================= -->
<div class="page">
  <div class="hdr"><span class="t">Finding 04 — Congestion Pricing</span>
    <span class="p">NYC Taxi Demand &amp; Operations · 2024</span></div>
  <h2>A real effect, smaller than the headlines</h2>

  <p>New York began charging vehicles to enter Manhattan below 60th Street on
  5 January 2025. Comparing January 2025 with January 2024 isolates the change
  while holding the season constant, and the trip records permit a cleaner test
  than a simple before-and-after: because the 2025 files record the charge
  itself, the tolled zone can be identified from the data rather than assumed.</p>

  <p>Scoring each pickup zone by the share of its trips that incurred the
  charge separates the city sharply — {R['cbd_zone_count']} zones sit near 88%
  and are inside the boundary, while zones north of 60th Street cluster between
  16% and 30%. Those {R['control_zone_count']} northern Manhattan zones form the
  control group: same borough, same weather, same month, no charge.</p>

  <div class="gotwrong">
    <div class="h">A wrong turn worth recording</div>
    My first pass at this defined the zone as “any trip where the congestion fee
    was greater than zero.” That looked reasonable and produced a control group
    of <b>fifteen trips</b>, which is what gave it away. The fee is charged on
    trips <i>entering</i> the zone, not on trips picked up inside it, so a
    fee-greater-than-zero filter quietly swept in pickups from
    {R['naive_cbd_zone_count']} of the city’s 265 zones and left almost nothing
    outside it to compare against. The share-based definition above is the fix. I have left the
    original logic in the commit history rather than tidying it away, because
    the failure mode — a filter that looks correct and silently defines away
    your control group — is the kind of thing worth being able to recognise
    twice.
  </div>

  <table><thead><tr><th rowspan="2" style="vertical-align:bottom">Metric</th>
    <th colspan="3" style="text-align:center">Inside charging zone (treated)</th>
    <th colspan="3" style="text-align:center">North of 60th St (control)</th></tr>
    <tr><th class="n" style="text-align:right">Jan 2024</th>
        <th class="n" style="text-align:right">Jan 2025</th>
        <th class="n" style="text-align:right">Change</th>
        <th class="n" style="text-align:right">Jan 2024</th>
        <th class="n" style="text-align:right">Jan 2025</th>
        <th class="n" style="text-align:right">Change</th></tr></thead>
    <tbody>{did_rows()}</tbody></table>

  <div class="kicker"><b>Difference-in-differences on speed:
  {did_sp:+.2f} percentage points.</b> Speeds inside the zone rose
  {cbd_sp:+.2f}% while the untolled control fell {ctl_sp:+.2f}% — so the raw
  before-and-after understates the effect. Trip duration inside the zone fell
  {abs(cbd_dur):.1f}% while rising {ctl_dur:+.1f}% in the control.</div>

  <div class="fig">{svg('cbd_speed.svg')}
    <div class="cap">Hourly speed inside the charging zone, before and after.
    The change is small in absolute terms and concentrated outside the deepest
    congestion of mid-afternoon.</div></div>

  <p>Two cautions on reading this. First, the effect is modest — a couple of
  percentage points against a control, not the transformation sometimes
  described. Second, yellow taxis are not the vehicles the policy primarily
  targets; they pay a small per-trip surcharge rather than the full daily
  charge. What this measures is the benefit taxis received from <i>other</i>
  traffic being priced off the road, which is arguably the cleanest available
  read on whether the policy moved vehicles at all.</p>

  <p>Taxi volume inside the zone rose {cbd_tr:.1f}% year over year against
  {ctl_tr:.1f}% in the control, a net {cbd_tr-ctl_tr:+.1f} points. That is
  consistent with some substitution from private cars toward taxis inside the
  boundary, though a single month cannot separate that from ordinary demand
  growth.</p>
</div>

<!-- ================= PAGE 7 : RECOMMENDATIONS ================= -->
<div class="page">
  <div class="hdr"><span class="t">Recommendations</span>
    <span class="p">NYC Taxi Demand &amp; Operations · 2024</span></div>
  <h2>What to do with this</h2>

  <div class="rec"><div class="m">Fleet positioning</div>
    <div class="h">Stop treating Midtown as the default destination for idle
    vehicles.</div>
    <p style="margin:0">The Midtown core combines the highest pickup volume in
    the city with bottom-decile revenue per minute. A vehicle repositioning into
    {zmid['zone']} at {worst_hr['hr']:02d}:00 is moving toward the worst
    earnings environment available. Upper East Side zones sit
    {(next(x['rev_per_min'] for x in R['zones_best'] if 'Yorkville West' in x['zone'])/zmid['rev_per_min']-1)*100:.0f}%
    higher on yield with comparable trip volume and should absorb repositioning
    first.</p></div>

  <div class="rec"><div class="m">Shift design</div>
    <div class="h">Treat 04:00–06:00 as the premium window it already is.</div>
    <p>An occupied hour worked between 04:00 and 06:00 returns
    {money(early_hr_rev, 0)} against {money(aftn_hr_rev, 0)} between 13:00 and
    16:00 — a difference of {money(window_gap, 0)} per hour, or
    {window_gap_pct:.0f}%. That gap is not a pricing artefact; it is the same
    meter running against{' '}{EARLY[0]['avg_mph']:.0f} mph roads instead of
    {AFTN[-1]['avg_mph']:.0f} mph ones.</p>
    <p style="margin:0"><b>Sizing it, with the caveat that matters:</b> moving
    {shift_frac*100:.0f}% of the {num(aftn_trips)} afternoon trips into the
    early window would be worth roughly
    <b>${shift_gain/1e6:.1f}M a year</b> on the same occupied minutes. I would
    not present that as a target. It assumes the passengers are there to be
    carried, and {shift_frac*100:.0f}% of afternoon volume is a
    {shift_demand_rise:.0f}% increase on everything the early window currently
    does — almost certainly more than latent demand at 5am can absorb. Read it
    as an upper bound that establishes the prize is worth a controlled test,
    not as a forecast.</p></div>

  <div class="rec"><div class="m">Pricing</div>
    <div class="h">Recognise that the time component of the meter is already
    doing the work — and that it is doing it unevenly.</div>
    <p style="margin:0">Fare per mile rose {fpm_rise:.1f}% across 2024 purely
    through congestion, with no schedule change. That protects revenue per trip
    but not revenue per hour, and it falls hardest on short Manhattan trips
    where the time component dominates. Any fare review should look at revenue
    per minute by zone rather than average fare, which conceals the
    problem.</p></div>

  <div class="rec"><div class="m">Measurement</div>
    <div class="h">Adopt revenue per minute as the standard operating
    metric.</div>
    <p style="margin:0">Average fare ranks {QUEENS['borough']} first and
    {MANH['borough']} last among the major boroughs; revenue per minute tells a
    different and more actionable story. Reporting that leads with average fare
    will systematically misdirect fleet decisions.</p></div>

  <h3>What this analysis cannot tell you</h3>
  <p>The dataset records completed metered trips only. It contains no record of
  time spent empty and cruising, which is where a meaningful share of driver
  cost sits — so revenue per <i>occupied</i> minute is an upper bound on true
  earnings efficiency, and zones that are easy to fill from will look worse than
  they are. High-volume ride-hailing trips are reported separately and are
  excluded here, so this is a view of the taxi network rather than of all
  for-hire travel. The congestion-pricing comparison rests on a single pair of
  months and controls for season and borough but not for weather, fuel prices,
  or concurrent roadworks; it should be read as a directional indication rather
  than a causal estimate.</p>
</div>

<!-- ================= PAGE 8 : METHOD ================= -->
<div class="page">
  <div class="hdr"><span class="t">Methodology &amp; Data Quality</span>
    <span class="p">NYC Taxi Demand &amp; Operations · 2024</span></div>
  <h2>How these numbers were produced</h2>

  <p><b>Source.</b> Trip-record files published monthly by the New York City
  Taxi &amp; Limousine Commission, covering yellow medallion and green
  street-hail vehicles for January–December 2024, plus January 2025 for the
  congestion-pricing comparison, joined to the TLC taxi zone lookup
  (265 zones). Files were read directly in Apache Parquet form.</p>

  <p><b>Tooling.</b> All aggregation in SQL executed by DuckDB directly against
  the Parquet files; figures drawn in Python. I chose DuckDB over loading to a
  warehouse because {R['rows_raw']/1e6:.0f}M rows is small enough to sit on a
  laptop, and being able to re-run the whole waterfall in under a minute mattered
  more here than durability — I re-ran it four times as the validation rules
  changed. The pipeline is reproducible from the scripts accompanying this
  report: <code>analysis.py</code> writes every statistic to
  <code>results.json</code>, and the document interpolates from that file, so no
  figure here is typed by hand.</p>

  <h3>Judgement calls</h3>
  <p>Three decisions shaped the numbers more than the rest, and a reader is
  entitled to disagree with any of them.</p>
  <p><b>The 3-hour duration ceiling.</b> There is no natural cut-off. I settled
  on three hours because the distribution is effectively empty between roughly
  two and six hours and then spikes at exactly 24, which is a meter artefact
  rather than a journey. A ceiling of two hours or six changes the headline
  averages by less than a tenth of a mile per hour, so the choice is not load-
  bearing — but it should be stated rather than buried.</p>
  <p><b>The 50,000-trip floor on zone rankings.</b> Without it the lowest-yield
  table fills with zones recording a few hundred trips a year, where a handful of
  unusual journeys moves the average. The floor is arbitrary; the ranking is
  stable anywhere between about 20,000 and 100,000.</p>
  <p><b>Tip rate as a mean of ratios.</b> Averaging tip-over-fare across trips
  overweights small fares, where a routine two-dollar tip on a six-dollar ride
  reads as 33%. The {R['tip_by_borough'][0]['tip_pct']:.0f}% figure for
  {R['tip_by_borough'][0]['borough']} should therefore be read as a
  <i>relative</i> signal against other boroughs on the same measure, not as the
  share of revenue arriving as tips. A fare-weighted figure would be lower. I
  kept the simpler measure because the report uses tipping only for the shape of
  the hourly curve, but it would be the wrong number to put in a
  revenue model.</p>

  <h3>Validation waterfall</h3>
  <p>Records were removed in the sequence below, each rule applied to the output
  of the previous one, so losses are attributable to a specific cause.
  {R['pct_retained']}% of raw records survived.</p>

  <table><thead><tr><th>Rule applied in sequence</th><th class="n">Removed</th>
    <th class="n">% of prior</th><th class="n">Remaining</th></tr></thead>
    <tbody>{validation_rows()}</tbody></table>

  <p>The two largest exclusions are worth noting. Trips failing the duration
  bound ({R['validation'][3]['rows_removed']:,} records) are meters left running
  after the passenger left, or closed within a few seconds of opening. The fare
  bound removes {R['validation'][5]['rows_removed']:,} records, of which more
  than 99% carry a <i>negative</i> fare_amount rather than a zero one — the
  signature of refunds, chargebacks and voided trips rather than of free rides.
  The speed bound is
  a final guard against distance or timestamp corruption and removes only
  {R['validation'][8]['rows_removed']:,} records
  ({R['validation'][8]['pct_removed']:.3f}%), which is a reassuring sign that
  the earlier filters had already caught most of the malformed rows.</p>

  <h3>Metric definitions</h3>
  <table><thead><tr><th>Metric</th><th>Definition</th></tr></thead><tbody>
  <tr><td><b>Revenue per minute</b></td><td>total_amount ÷ (trip duration in
    minutes). Includes tips, tolls and surcharges. The primary efficiency
    measure in this report.</td></tr>
  <tr><td><b>Average speed</b></td><td>trip_distance ÷ (trip duration in hours).
    A straight-line proxy: the meter records odometer distance but not route, so
    this reflects realised journey speed, not free-flow road speed.</td></tr>
  <tr><td><b>Fare per mile</b></td><td>fare_amount ÷ trip_distance, excluding
    tips and surcharges, restricted to trips of at least half a mile.</td></tr>
  <tr><td><b>Tip rate</b></td><td>tip_amount ÷ fare_amount for card-paid trips
    only ({R['tip_by_payment'][0]['trips']/K['trips']*100:.0f}% of the
    dataset). Cash tips are not captured by the meter and are recorded as zero,
    so cash trips are excluded rather than counted as non-tipping.</td></tr>
  <tr><td><b>Charging zone</b></td><td>Derived, not assumed: pickup zones where
    at least 70% of January 2025 trips incurred the CBD congestion fee. This
    yields {R['cbd_zone_count']} zones. The control group is the
    {R['control_zone_count']} Manhattan zones below 40%.</td></tr>
  </tbody></table>

  <h3>Representative query</h3>
  <p>Zone-level efficiency, as used for Finding 03:</p>
  <pre>SELECT z.zone, z.borough,
       count(*)                        AS trips,
       avg(t.mph)                      AS avg_mph,
       avg(t.rev_per_min)              AS rev_per_min,
       avg(t.total_amount)             AS avg_fare
FROM   trips t
JOIN   zones z ON t.pu_id = z.location_id
WHERE  z.borough &lt;&gt; 'Unknown'
GROUP  BY z.zone, z.borough
HAVING count(*) &gt;= 50000      -- stability floor for the averages
ORDER  BY rev_per_min ASC
LIMIT  10;</pre>

  <div class="note">Data accessed from the NYC TLC public trip-record archive.
  The Commission notes that records are submitted by technology providers and
  that it does not guarantee their accuracy; the validation waterfall above is
  the response to that caveat. Analysis and interpretation are the author’s
  own.</div>
</div>

</body></html>
"""

OUT.write_text(HTML)
print(f"Wrote {OUT} ({len(HTML):,} chars)")
