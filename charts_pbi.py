"""
Dashboard-page chart set, styled to Power BI conventions.

Differences from charts.py (which serves the narrative pages):
  - Power BI default theme palette
  - Segoe UI where available, Tahoma as the metric-similar fallback
  - No titles inside the SVG; the card header carries the title, as in PBI
  - Horizontal gridlines only, no axis spines, label-first formatting
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

ROOT = Path(__file__).parent
CH = ROOT / "charts"
CH.mkdir(exist_ok=True)
R = json.loads((ROOT / "results.json").read_text())

# Power BI default theme
BLUE = "#118DFF"
NAVY = "#12239E"
ORANGE = "#E66C37"
PURPLE = "#6B007B"
PINK = "#E044A7"
VIOLET = "#744EC2"
GOLD = "#D9B300"
RED = "#D64550"
TEAL = "#0F9CA0"

INK = "#252423"      # PBI primary text
SUB = "#605E5C"      # PBI secondary text
GRIDC = "#E1DFDD"    # PBI gridline

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Segoe UI", "Tahoma", "Verdana", "DejaVu Sans"],
    "svg.fonttype": "path",
    "text.color": INK,
    "axes.labelcolor": SUB,
    "xtick.color": SUB,
    "ytick.color": SUB,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": GRIDC,
    "grid.linewidth": 0.8,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "xtick.labelsize": 8.5,
    "ytick.labelsize": 8.5,
})


def pbi(ax, xgrid=False):
    for s in ax.spines.values():
        s.set_visible(False)
    ax.grid(axis="y")
    ax.grid(axis="x", visible=xgrid)
    ax.tick_params(length=0)


def save(fig, name):
    fig.tight_layout(pad=0.35)
    fig.savefig(CH / name, format="svg", bbox_inches="tight")
    plt.close(fig)
    print(f"  charts/{name}")


# --------------------------------------------------- monthly column + line
def monthly():
    m = R["monthly"]
    lab = [x["month"][5:] for x in m]
    trips = [x["trips"] / 1e6 for x in m]
    fare = [x["avg_fare"] for x in m]

    fig, ax = plt.subplots(figsize=(6.4, 2.5))
    ax.bar(lab, trips, color=BLUE, width=.66)
    ax.set_ylabel("Trips (M)", fontsize=8.5)
    pbi(ax)
    ax2 = ax.twinx()
    ax2.plot(lab, fare, color=ORANGE, lw=2.2, marker="o", ms=3.6)
    ax2.set_ylabel("Avg fare ($)", fontsize=8.5, color=SUB)
    ax2.grid(False)
    for s in ax2.spines.values():
        s.set_visible(False)
    ax2.tick_params(length=0, labelsize=8.5)
    save(fig, "pbi_monthly.svg")


# ------------------------------------------------------------- donut
def donut():
    names = {1: "Credit card", 2: "Cash", 0: "Unknown", 4: "Dispute",
             3: "No charge"}
    rows = [r for r in R["tip_by_payment"] if r["payment_type"] is not None]
    rows = sorted(rows, key=lambda r: -r["trips"])[:4]
    vals = [r["trips"] for r in rows]
    labs = [names.get(int(r["payment_type"]), "Other") for r in rows]
    cols = [BLUE, NAVY, ORANGE, GOLD]
    tot = sum(vals)

    fig, ax = plt.subplots(figsize=(2.75, 2.5))
    w, _ = ax.pie(vals, colors=cols, startangle=90,
                  wedgeprops=dict(width=.42, edgecolor="white", linewidth=1.6))
    ax.text(0, .07, f"{tot/1e6:.1f}M", ha="center", va="center",
            fontsize=15, fontweight="bold", color=INK)
    ax.text(0, -.19, "trips", ha="center", va="center", fontsize=8.5,
            color=SUB)
    ax.legend(w, [f"{l}  {v/tot*100:.0f}%" for l, v in zip(labs, vals)],
              loc="center left", bbox_to_anchor=(.98, .5), frameon=False,
              fontsize=7.8, handlelength=.85, handleheight=.85, labelspacing=.55)
    ax.set_aspect("equal")
    save(fig, "pbi_donut.svg")


# ------------------------------------------------------------- heatmap
def heatmap():
    g = np.zeros((7, 24))
    for r in R["heatmap"]:
        g[int(r["dow"]), int(r["hr"])] = r["trips"]
    g = g[[1, 2, 3, 4, 5, 6, 0]] / 1000.0
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    cmap = LinearSegmentedColormap.from_list(
        "pbi", ["#FFFFFF", "#CFE7FF", "#67B3FF", "#118DFF", "#12239E"])

    fig, ax = plt.subplots(figsize=(6.4, 2.15))
    im = ax.imshow(g, aspect="auto", cmap=cmap)
    ax.set_xticks(range(0, 24, 2))
    ax.set_xticklabels([f"{h:02d}" for h in range(0, 24, 2)])
    ax.set_yticks(range(7))
    ax.set_yticklabels(names, fontsize=8.5)
    ax.grid(False)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, pad=.012, fraction=.032)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=7.2, length=0)
    save(fig, "pbi_heatmap.svg")


# --------------------------------------------------------- speed / yield
def speed():
    h = R["hourly"]
    hrs = [x["hr"] for x in h]
    mph = [x["avg_mph"] for x in h]
    rpm = [x["rev_per_min"] for x in h]

    fig, ax = plt.subplots(figsize=(9.1, 2.35))
    ax.plot(hrs, mph, color=BLUE, lw=2.4, marker="o", ms=3.4, label="Avg mph")
    ax.set_ylabel("Avg speed (mph)", fontsize=8.5)
    ax.set_xticks(range(0, 24, 1))
    ax.set_xticklabels([f"{x:02d}" for x in range(0, 24)], fontsize=7.6)
    pbi(ax)
    ax2 = ax.twinx()
    ax2.plot(hrs, rpm, color=ORANGE, lw=2.2, ls="--", label="Rev/min")
    ax2.set_ylabel("Revenue / min ($)", fontsize=8.5, color=SUB)
    ax2.grid(False)
    for s in ax2.spines.values():
        s.set_visible(False)
    ax2.tick_params(length=0, labelsize=8.5)
    ln = ax.get_lines() + ax2.get_lines()
    ax.legend(ln, [l.get_label() for l in ln], loc="upper center", ncol=2,
              frameon=False, fontsize=8, bbox_to_anchor=(.5, 1.16))
    save(fig, "pbi_speed.svg")


# ------------------------------------------------------------- borough bar
def borough():
    b = [x for x in R["borough"] if x["trips"] >= 100000]
    b = sorted(b, key=lambda x: x["rev_per_min"])
    fig, ax = plt.subplots(figsize=(2.95, 2.15))
    cols = [RED if x["rev_per_min"] < R["kpi"]["avg_rev_per_min"] else BLUE
            for x in b]
    ax.barh([x["borough"] for x in b], [x["rev_per_min"] for x in b],
            color=cols, height=.6)
    ax.axvline(R["kpi"]["avg_rev_per_min"], color=SUB, ls=":", lw=1.2)
    ax.set_xlabel("Revenue / min ($)", fontsize=8.5)
    pbi(ax)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x")
    for i, x in enumerate(b):
        ax.text(x["rev_per_min"], i, f" {x['rev_per_min']:.2f}", va="center",
                fontsize=7.8, color=SUB)
    save(fig, "pbi_borough.svg")


# --------------------------------------------------------- zone yield bar
def zones():
    z = sorted(R["zones_worst"][:6], key=lambda x: x["rev_per_min"])
    # Zone names are long and the card is narrow; shorten on the separator
    # rather than hard-truncating mid-word.
    def short(n):
        n = n.split("/")[0]
        return n if len(n) <= 18 else n[:17] + "…"

    fig, ax = plt.subplots(figsize=(2.9, 2.25))
    ax.barh([short(x["zone"]) for x in z], [x["rev_per_min"] for x in z],
            color=RED, height=.62)
    ax.axvline(R["kpi"]["avg_rev_per_min"], color=SUB, ls=":", lw=1.2)
    ax.set_xlabel("Revenue / min ($)", fontsize=8.2)
    pbi(ax)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x")
    ax.tick_params(axis="y", labelsize=8.2)
    ax.tick_params(axis="x", labelsize=7.8)
    save(fig, "pbi_zones.svg")


if __name__ == "__main__":
    print("Power BI-styled dashboard visuals:")
    monthly(); donut(); heatmap(); speed(); borough(); zones()
    print("Done.")
