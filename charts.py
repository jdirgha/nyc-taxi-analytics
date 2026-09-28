"""
Chart generation for the NYC taxi report.
Reads results.json (produced by analysis.py) and writes SVGs into charts/.
Nothing here computes a statistic — it only draws what analysis.py measured.
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

ROOT = Path(__file__).parent
CHARTS = ROOT / "charts"
CHARTS.mkdir(exist_ok=True)
R = json.loads((ROOT / "results.json").read_text())

INK = "#16202b"
PRIMARY = "#1f4e79"
ACCENT = "#d97706"
TEAL = "#0f766e"
RED = "#b91c1c"
GRID = "#dfe4ea"
MUTED = "#6b7280"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "svg.fonttype": "path",
    "axes.edgecolor": GRID,
    "axes.labelcolor": INK,
    "text.color": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.7,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})


def finish(fig, name):
    fig.tight_layout()
    fig.savefig(CHARTS / name, format="svg", bbox_inches="tight",
                transparent=False)
    plt.close(fig)
    print(f"  wrote charts/{name}")


def strip(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


# ---------------------------------------------------------------- monthly
def monthly_trend():
    m = R["monthly"]
    labels = [x["month"][5:] for x in m]
    trips = [x["trips"] / 1e6 for x in m]
    fare = [x["avg_fare"] for x in m]

    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.bar(labels, trips, color=PRIMARY, alpha=.85, width=.62,
           label="Trips (millions)")
    ax.set_ylabel("Trips (millions)", color=PRIMARY)
    ax.tick_params(axis="y", labelcolor=PRIMARY)
    ax.grid(axis="x", visible=False)
    strip(ax)

    ax2 = ax.twinx()
    ax2.plot(labels, fare, color=ACCENT, lw=2.6, marker="o", ms=5,
             label="Avg total fare")
    ax2.set_ylabel("Average total fare ($)", color=ACCENT)
    ax2.tick_params(axis="y", labelcolor=ACCENT)
    ax2.grid(False)
    for s in ("top", "left", "right"):
        ax2.spines[s].set_visible(False)

    ax.set_title("Trip volume and average fare by month, 2024",
                 loc="left", fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel("Month of 2024")
    finish(fig, "monthly_trend.svg")


# ---------------------------------------------------------------- heatmap
def demand_heatmap():
    grid = np.zeros((7, 24))
    for row in R["heatmap"]:
        grid[int(row["dow"]), int(row["hr"])] = row["trips"]
    # DuckDB dayofweek: 0 = Sunday
    order = [1, 2, 3, 4, 5, 6, 0]
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    grid = grid[order] / 1000.0

    cmap = LinearSegmentedColormap.from_list(
        "demand", ["#f8fafc", "#bfdbfe", "#3b82f6", "#1e3a8a", "#0b1f4b"])

    fig, ax = plt.subplots(figsize=(9, 3.2))
    im = ax.imshow(grid, aspect="auto", cmap=cmap, interpolation="nearest")
    ax.set_xticks(range(0, 24, 2))
    ax.set_xticklabels([f"{h:02d}" for h in range(0, 24, 2)])
    ax.set_yticks(range(7))
    ax.set_yticklabels(names)
    ax.set_xlabel("Hour of day (pickup)")
    ax.grid(False)
    ax.set_title("Pickup volume by day of week and hour (thousands of trips)",
                 loc="left", fontsize=12, fontweight="bold", pad=12)
    cb = fig.colorbar(im, ax=ax, pad=.015)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=8)
    finish(fig, "demand_heatmap.svg")


# ------------------------------------------------------- speed vs yield
def hourly_speed_yield():
    h = R["hourly"]
    hrs = [x["hr"] for x in h]
    mph = [x["avg_mph"] for x in h]
    rpm = [x["rev_per_min"] for x in h]

    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.plot(hrs, mph, color=TEAL, lw=2.8, marker="o", ms=4)
    ax.set_ylabel("Average speed (mph)", color=TEAL)
    ax.tick_params(axis="y", labelcolor=TEAL)
    ax.set_xlabel("Hour of day (pickup)")
    ax.set_xticks(range(0, 24, 2))
    strip(ax)

    slow = min(h, key=lambda x: x["avg_mph"])
    ax.annotate(f"slowest hour: {slow['hr']:02d}:00 — {slow['avg_mph']:.1f} mph",
                xy=(slow["hr"], slow["avg_mph"]),
                xytext=(slow["hr"] + 1.2, slow["avg_mph"] + 1.6),
                fontsize=9, color=RED,
                arrowprops=dict(arrowstyle="->", color=RED, lw=1.2))

    ax2 = ax.twinx()
    ax2.plot(hrs, rpm, color=ACCENT, lw=2.2, ls="--")
    ax2.set_ylabel("Revenue per minute ($)", color=ACCENT)
    ax2.tick_params(axis="y", labelcolor=ACCENT)
    ax2.grid(False)
    for s in ("top", "left", "right"):
        ax2.spines[s].set_visible(False)

    ax.set_title("Traffic speed and revenue per minute across the day",
                 loc="left", fontsize=12, fontweight="bold", pad=12)
    finish(fig, "hourly_speed_yield.svg")


# ---------------------------------------------------------------- borough
def borough_chart():
    b = [x for x in R["borough"]][:6]
    b = sorted(b, key=lambda x: x["trips"])
    names = [x["borough"] for x in b]
    trips = [x["trips"] / 1e6 for x in b]
    rpm = [x["rev_per_min"] for x in b]

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.1))
    a = axes[0]
    a.barh(names, trips, color=PRIMARY, alpha=.88, height=.6)
    a.set_xlabel("Trips (millions)")
    a.set_title("Pickup volume by borough", loc="left", fontsize=11,
                fontweight="bold", pad=10)
    a.grid(axis="y", visible=False)
    strip(a)
    for i, v in enumerate(trips):
        a.text(v, i, f" {v:.2f}M", va="center", fontsize=8.5, color=MUTED)

    a = axes[1]
    a.barh(names, rpm, color=TEAL, alpha=.88, height=.6)
    a.set_xlabel("Revenue per minute ($)")
    a.set_title("Revenue efficiency by borough", loc="left", fontsize=11,
                fontweight="bold", pad=10)
    a.grid(axis="y", visible=False)
    strip(a)
    for i, v in enumerate(rpm):
        a.text(v, i, f" ${v:.2f}", va="center", fontsize=8.5, color=MUTED)

    finish(fig, "borough.svg")


# ------------------------------------------------------------ worst zones
def worst_zones():
    z = sorted(R["zones_worst"], key=lambda x: -x["rev_per_min"])
    names = [f"{x['zone'][:30]}" for x in z]
    rpm = [x["rev_per_min"] for x in z]
    overall = R["kpi"]["avg_rev_per_min"]

    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.barh(names, rpm, color=RED, alpha=.78, height=.62)
    ax.axvline(overall, color=INK, ls="--", lw=1.4)
    ax.text(overall, len(names) - .3, f"  city average ${overall:.2f}",
            fontsize=9, color=INK, va="top")
    ax.set_xlabel("Revenue per minute ($)")
    ax.set_title("Lowest-yield pickup zones (minimum 50,000 trips)",
                 loc="left", fontsize=12, fontweight="bold", pad=12)
    ax.grid(axis="y", visible=False)
    strip(ax)
    finish(fig, "worst_zones.svg")


# ---------------------------------------------------------------- tipping
def tipping():
    t = R["tip_by_hour"]
    hrs = [x["hr"] for x in t]
    pct = [x["tip_pct"] for x in t]

    fig, ax = plt.subplots(figsize=(9, 2.9))
    ax.plot(hrs, pct, color=ACCENT, lw=2.8, marker="o", ms=4)
    ax.fill_between(hrs, pct, min(pct) - .3, color=ACCENT, alpha=.12)
    ax.set_xticks(range(0, 24, 2))
    ax.set_xlabel("Hour of day (pickup)")
    ax.set_ylabel("Average tip (% of fare)")
    ax.set_title("Card tip rate by hour of day",
                 loc="left", fontsize=12, fontweight="bold", pad=12)
    strip(ax)
    finish(fig, "tipping.svg")


# ------------------------------------------------------ congestion pricing
def cbd_speed():
    a = {x["hr"]: x["avg_mph"] for x in R["cbd_hourly_2024"]}
    b = {x["hr"]: x["avg_mph"] for x in R["cbd_hourly_2025"]}
    hrs = sorted(set(a) & set(b))
    va = [a[h] for h in hrs]
    vb = [b[h] for h in hrs]

    fig, ax = plt.subplots(figsize=(9, 3.4))
    ax.plot(hrs, va, color=MUTED, lw=2.4, marker="o", ms=4,
            label="January 2024 (before)")
    ax.plot(hrs, vb, color=TEAL, lw=2.8, marker="o", ms=4,
            label="January 2025 (after)")
    ax.fill_between(hrs, va, vb, where=[y > x for x, y in zip(va, vb)],
                    color=TEAL, alpha=.14)
    ax.set_xticks(range(0, 24, 2))
    ax.set_xlabel("Hour of day (pickup)")
    ax.set_ylabel("Average speed (mph)")
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    ax.set_title("Congestion-zone travel speed before and after CBD tolling",
                 loc="left", fontsize=12, fontweight="bold", pad=12)
    strip(ax)
    finish(fig, "cbd_speed.svg")


if __name__ == "__main__":
    print("Generating charts...")
    monthly_trend()
    demand_heatmap()
    hourly_speed_yield()
    borough_chart()
    worst_zones()
    tipping()
    cbd_speed()
    print("Done.")
