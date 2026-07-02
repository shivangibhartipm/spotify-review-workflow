"""Phase 5 - Streamlit dashboard.

Run:
    streamlit run dashboard/app.py
"""

from __future__ import annotations

import json
import sqlite3
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = ROOT_DIR / "data" / "reviews.db"

THEME_LABELS = {
    "DISCOVERY_PROBLEMS": "Discovery Problems",
    "RECOMMENDATION_FRUSTRATIONS": "Recommendation Frustrations",
    "REPEAT_LISTENING_CAUSES": "Repeat Listening Causes",
    "UNMET_NEEDS": "Unmet Needs",
    "LISTENING_GOALS": "Listening Goals",
    "UNCLASSIFIED": "Unclassified",
}

THEME_ORDER = [
    "DISCOVERY_PROBLEMS",
    "RECOMMENDATION_FRUSTRATIONS",
    "REPEAT_LISTENING_CAUSES",
    "UNMET_NEEDS",
    "LISTENING_GOALS",
]

THEME_COLORS = {
    "DISCOVERY_PROBLEMS": "#e8a54b",
    "RECOMMENDATION_FRUSTRATIONS": "#d65f58",
    "REPEAT_LISTENING_CAUSES": "#9b84d9",
    "UNMET_NEEDS": "#6c91e8",
    "LISTENING_GOALS": "#66b8a8",
    "UNCLASSIFIED": "#6b6560",
}

SOURCE_LABELS = {
    "app_store": "App Store",
    "play_store": "Play Store",
    "forum": "Community Forum",
    "forums": "Community Forum",
    "social": "Social",
}


def inject_styles() -> None:
    """Apply the dark editorial style used by the dashboard reference."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Instrument+Serif:ital,wght@0,400;0,600;1,400&display=swap');

        :root {
            --bg: #15161b;
            --panel: #1d2028;
            --panel-soft: #171a21;
            --border: rgba(255,255,255,0.07);
            --text: #f3eee6;
            --muted: #9a948c;
            --dim: #6d6862;
            --accent: #e8a54b;
            --teal: #62b8ad;
            --red: #d65f58;
        }

        .stApp {
            background:
                radial-gradient(circle at 15% 0%, rgba(232,165,75,0.05), transparent 25%),
                linear-gradient(180deg, #14151a 0%, #171922 100%);
            color: var(--text);
        }

        .block-container {
            max-width: 1240px;
            padding: 2.1rem 2rem 4rem;
        }

        header[data-testid="stHeader"],
        div[data-testid="stToolbar"],
        div[data-testid="stDecoration"] {
            display: none;
        }

        .dashboard-header {
            display: flex;
            justify-content: space-between;
            gap: 2rem;
            align-items: flex-start;
            margin-bottom: 2.2rem;
        }

        .eyebrow {
            display: inline-flex;
            align-items: center;
            gap: 0.65rem;
            color: #1ed760;
            font: 600 1.05rem 'DM Mono', monospace;
            letter-spacing: 0.16em;
            text-transform: uppercase;
            margin-bottom: 0.65rem;
        }

        .spotify-logo {
            width: 1.65rem;
            height: 1.65rem;
            flex: 0 0 auto;
        }

        .hero-title {
            color: #fffaf1;
            font-family: 'Instrument Serif', Georgia, serif;
            font-size: clamp(2.5rem, 5vw, 3.7rem);
            line-height: 1.08;
            letter-spacing: 0.02em;
            margin: 0.15rem 0 1rem;
            padding: 0.1rem 0;
            text-shadow: 0 2px 24px rgba(232, 165, 75, 0.16);
        }

        .hero-subtitle,
        .section-note,
        .meta-text {
            color: var(--muted);
            font: 0.78rem/1.65 'DM Mono', monospace;
        }

        .hero-subtitle {
            max-width: 760px;
        }

        .header-meta {
            color: var(--dim);
            font: 0.72rem/1.7 'DM Mono', monospace;
            text-align: right;
            white-space: nowrap;
            padding-top: 3.1rem;
        }

        .status-dot {
            display: inline-block;
            width: 0.45rem;
            height: 0.45rem;
            border-radius: 999px;
            background: var(--teal);
            box-shadow: 0 0 12px rgba(98,184,173,0.65);
            margin-right: 0.35rem;
        }

        .metric-card,
        .panel,
        .opportunities-panel,
        .explorer-panel {
            background: linear-gradient(180deg, rgba(31,34,43,0.98), rgba(28,31,40,0.98));
            border: 1px solid var(--border);
            border-radius: 0.45rem;
            box-shadow: 0 18px 70px rgba(0,0,0,0.22);
        }

        .metric-card {
            min-height: 9.5rem;
            padding: 1.05rem 1.15rem 0.95rem;
        }

        .metric-label,
        .table-label {
            color: var(--dim);
            font: 500 0.64rem 'DM Mono', monospace;
            letter-spacing: 0.16em;
            text-transform: uppercase;
        }

        .metric-value {
            font-family: 'Instrument Serif', Georgia, serif;
            font-size: 2.55rem;
            line-height: 1;
            margin: 0.55rem 0 0.15rem;
        }

        .metric-value.teal { color: var(--teal); }
        .metric-value.red { color: var(--red); }

        .sparkline {
            display: flex;
            align-items: flex-end;
            gap: 0.22rem;
            height: 1.25rem;
            margin-top: 1.1rem;
        }

        .sparkline span {
            display: block;
            width: 0.22rem;
            min-height: 0.2rem;
            border-radius: 1px;
        }

        .panel {
            padding: 1.35rem 1.55rem 1.55rem;
            min-height: 22rem;
        }

        .section-title {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 1.35rem;
        }

        .section-title h2 {
            color: #fff6e8;
            font-family: 'Instrument Serif', Georgia, serif;
            font-size: 1.65rem;
            line-height: 1;
            margin: 0;
            text-shadow: 0 1px 18px rgba(255, 246, 232, 0.12);
        }

        .section-title h2::before {
            content: "";
            display: inline-block;
            width: 0.45rem;
            height: 0.45rem;
            border-radius: 999px;
            background: var(--accent);
            box-shadow: 0 0 14px rgba(232, 165, 75, 0.45);
            margin-right: 0.55rem;
            vertical-align: 0.12rem;
        }

        .theme-row {
            display: grid;
            grid-template-columns: minmax(8rem, 11rem) 1fr 2.2rem;
            align-items: center;
            gap: 0.9rem;
            margin: 0.7rem 0;
            font: 0.77rem 'DM Mono', monospace;
        }

        .theme-name,
        .segment-name {
            color: var(--text);
        }

        .bar-track {
            height: 0.95rem;
            background: #141721;
            border-radius: 0.2rem;
            overflow: hidden;
            box-shadow: inset 0 0 0 1px rgba(255,255,255,0.03);
        }

        .bar-fill {
            height: 100%;
            border-radius: 0.2rem;
        }

        .bar-count,
        .mention-count {
            color: var(--muted);
            text-align: right;
            font: 0.73rem 'DM Mono', monospace;
        }

        .segment-table {
            width: 100%;
            border-collapse: collapse;
            font: 0.72rem 'DM Mono', monospace;
        }

        .segment-table th {
            color: var(--dim);
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.13em;
            text-align: left;
            padding: 0 0.55rem 0.75rem;
        }

        .segment-table td {
            border-top: 1px solid rgba(255,255,255,0.06);
            color: var(--muted);
            padding: 0.72rem 0.55rem;
            vertical-align: middle;
        }

        .segment-table .mini-metric {
            display: grid;
            grid-template-columns: 4.7rem 2.3rem;
            gap: 0.55rem;
            align-items: center;
        }

        .mini-track {
            height: 0.32rem;
            background: #131720;
            border-radius: 99px;
            overflow: hidden;
        }

        .mini-fill {
            height: 100%;
            border-radius: 99px;
        }

        .opportunities-panel,
        .explorer-panel {
            padding: 1.35rem 1.55rem 1rem;
            margin-top: 1.1rem;
        }

        .opportunity-row {
            display: grid;
            grid-template-columns: 2.4rem 1fr auto;
            gap: 1rem;
            padding: 1rem 0;
            border-top: 1px solid rgba(255,255,255,0.055);
            align-items: start;
        }

        .rank {
            color: var(--accent);
            font-family: 'Instrument Serif', Georgia, serif;
            font-size: 1.35rem;
            font-weight: 600;
        }

        .opportunity-title {
            color: var(--text);
            font: 600 0.83rem 'DM Mono', monospace;
            margin-bottom: 0.18rem;
        }

        .opportunity-summary {
            color: #cfc7bc;
            font: 0.74rem/1.55 'DM Mono', monospace;
            margin-bottom: 0.22rem;
        }

        .quote {
            color: var(--muted);
            font: italic 0.9rem/1.65 'Instrument Serif', Georgia, serif;
        }

        .mention-count {
            color: var(--teal);
            white-space: nowrap;
        }

        .stSelectbox label,
        .stTextInput label {
            display: none;
        }

        div[data-baseweb="select"] > div,
        .stTextInput input {
            background: #131720 !important;
            border: 1px solid rgba(232,165,75,0.35) !important;
            color: var(--text) !important;
            border-radius: 0.25rem !important;
            font-family: 'DM Mono', monospace !important;
            font-size: 0.75rem !important;
        }

        div[data-testid="stTextInput"] input,
        div[data-testid="stTextInput"] input:focus {
            color: #fffaf1 !important;
            -webkit-text-fill-color: #fffaf1 !important;
            caret-color: var(--accent) !important;
        }

        div[data-testid="stTextInput"] input::placeholder {
            color: #8f8981 !important;
            -webkit-text-fill-color: #8f8981 !important;
            opacity: 1 !important;
        }

        div[data-testid="stCaptionContainer"],
        div[data-testid="stCaptionContainer"] p {
            color: #cfc7bc !important;
            font-family: 'DM Mono', monospace !important;
            font-size: 0.74rem !important;
        }

        .stDataFrame {
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 0.35rem;
            overflow: hidden;
        }

        @media (max-width: 900px) {
            .dashboard-header {
                display: block;
            }
            .header-meta {
                text-align: left;
                padding-top: 1rem;
            }
            .theme-row,
            .opportunity-row {
                grid-template-columns: 1fr;
            }
            .bar-count,
            .mention-count {
                text-align: left;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


st.set_page_config(
    page_title="AI Review Discovery Engine",
    page_icon="",
    layout="wide",
)


def _db_mtime() -> float:
    return DB_PATH.stat().st_mtime if DB_PATH.exists() else 0.0


@st.cache_data(show_spinner=False)
def load_reviews(_: float) -> pd.DataFrame:
    """Load enriched review data for dashboard filtering and drilldown."""
    if not DB_PATH.exists():
        return pd.DataFrame()

    query = """
        SELECT
            e.id,
            c.source,
            c.rating,
            c.date,
            c.url,
            c.clean_text,
            e.sentiment,
            e.sentiment_score,
            e.topic_label,
            e.topic_confidence,
            e.theme,
            e.segments
        FROM enriched_reviews e
        JOIN clean_reviews c ON c.id = e.id
        ORDER BY c.date DESC, e.id ASC
    """
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(query, conn)

    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    df["segment_list"] = df["segments"].apply(parse_segments)
    df["primary_segment"] = df["segment_list"].apply(
        lambda segments: segments[0] if segments else "Unknown"
    )
    df["segment_text"] = df["segment_list"].apply(lambda segments: ", ".join(segments))
    return df


@st.cache_data(show_spinner=False)
def load_insights(_: float) -> pd.DataFrame:
    """Load precomputed Phase 4 insights."""
    if not DB_PATH.exists():
        return pd.DataFrame()

    query = """
        SELECT insight_type, label, count, example_ids, summary
        FROM insights
        ORDER BY insight_type ASC, count DESC, label ASC
    """
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(query, conn)


def parse_segments(raw_segments: str | None) -> list[str]:
    """Parse JSON segment list from enriched_reviews."""
    if not raw_segments:
        return ["Unknown"]
    try:
        parsed = json.loads(raw_segments)
    except json.JSONDecodeError:
        return ["Unknown"]

    if not isinstance(parsed, list):
        return ["Unknown"]

    segments = [
        str(item.get("segment", "Unknown"))
        for item in parsed
        if isinstance(item, dict) and item.get("segment")
    ]
    return segments or ["Unknown"]


def parse_example_ids(raw_example_ids: str | None) -> list[str]:
    """Parse example_ids JSON from insights."""
    if not raw_example_ids:
        return []
    try:
        parsed = json.loads(raw_example_ids)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def metric_value(df: pd.DataFrame, column: str, value: str) -> int:
    return int((df[column] == value).sum()) if column in df else 0


def pct(part: int, whole: int) -> int:
    return round((part / whole) * 100) if whole else 0


def theme_label(theme: str | None) -> str:
    return THEME_LABELS.get(str(theme), str(theme or "Unknown").replace("_", " ").title())


def source_label(source: str | None) -> str:
    return SOURCE_LABELS.get(str(source), str(source or "Unknown").replace("_", " ").title())


def truncate_text(text: str | None, limit: int = 140) -> str:
    clean = " ".join(str(text or "").split())
    return clean if len(clean) <= limit else f"{clean[: limit - 1].rstrip()}..."


def date_range_label(reviews: pd.DataFrame) -> str:
    dates = reviews["date"].dropna() if "date" in reviews else pd.Series(dtype="datetime64[ns]")
    if dates.empty:
        return ""
    start = dates.min().strftime("%b")
    end = dates.max().strftime("%b %Y")
    return f"{start} — {end}"


def sparkline_html(color: str, values: list[int] | None = None) -> str:
    values = values or [4, 8, 5, 11, 7, 13, 9, 15, 12, 10]
    max_value = max(values) or 1
    bars = "".join(
        f"<span style='height:{max(18, int(value / max_value * 100))}%;"
        f"background:{color};opacity:{0.45 + (idx / max(len(values), 1)) * 0.5:.2f}'></span>"
        for idx, value in enumerate(values)
    )
    return f"<div class='sparkline'>{bars}</div>"


def metric_card(label: str, value: str, subtext: str, color: str = "", bars: list[int] | None = None) -> str:
    color_class = f" {color}" if color else ""
    spark_color = {"teal": "var(--teal)", "red": "var(--red)"}.get(color, "var(--accent)")
    return (
        "<div class='metric-card'>"
        f"<div class='metric-label'>{escape(label)}</div>"
        f"<div class='metric-value{color_class}'>{escape(value)}</div>"
        f"<div class='meta-text'>{escape(subtext)}</div>"
        f"{sparkline_html(spark_color, bars)}"
        "</div>"
    )


def section_title(title: str, note: str) -> str:
    return (
        "<div class='section-title'>"
        f"<h2>{escape(title)}</h2>"
        f"<div class='section-note'>{escape(note)}</div>"
        "</div>"
    )


def insight_table(insights: pd.DataFrame, insight_type: str, limit: int = 10) -> pd.DataFrame:
    if insights.empty:
        return pd.DataFrame(columns=["label", "count", "summary"])
    return (
        insights[insights["insight_type"] == insight_type]
        .head(limit)[["label", "count", "summary"]]
        .reset_index(drop=True)
    )


def bar_chart(df: pd.DataFrame, x: str, y: str, title: str):
    if df.empty:
        st.info(f"No data available for {title.lower()}.")
        return
    st.bar_chart(df.set_index(x)[y])


def show_examples(reviews: pd.DataFrame, example_ids: list[str]) -> None:
    """Render representative excerpts for a selected insight."""
    if not example_ids:
        st.caption("No representative excerpts stored for this insight.")
        return

    examples = reviews[reviews["id"].isin(example_ids)].copy()
    if examples.empty:
        st.caption("Representative review IDs were not found in the review table.")
        return

    for _, row in examples.iterrows():
        with st.expander(f"{row['source']} | {row['sentiment']} | {row['theme']}"):
            st.write(row["clean_text"])
            st.caption(f"Topic: {row['topic_label']} | Segment: {row['segment_text']}")
            if row.get("url"):
                st.link_button("Open source", row["url"])


def selected_insight_examples(
    reviews: pd.DataFrame,
    insights: pd.DataFrame,
    insight_type: str,
    label: str,
) -> None:
    row = insights[
        (insights["insight_type"] == insight_type) & (insights["label"] == label)
    ]
    if row.empty:
        return
    st.subheader("Representative Excerpts")
    show_examples(reviews, parse_example_ids(row.iloc[0]["example_ids"]))


def overview_tab(reviews: pd.DataFrame) -> None:
    total = len(reviews)
    positive = metric_value(reviews, "sentiment", "positive")
    neutral = metric_value(reviews, "sentiment", "neutral")
    negative = metric_value(reviews, "sentiment", "negative")
    discovery = metric_value(reviews, "theme", "DISCOVERY_PROBLEMS")
    recommendation = metric_value(reviews, "theme", "RECOMMENDATION_FRUSTRATIONS")

    cols = st.columns(6)
    cols[0].metric("Total Reviews", f"{total:,}")
    cols[1].metric("Positive", f"{positive:,}")
    cols[2].metric("Neutral", f"{neutral:,}")
    cols[3].metric("Negative", f"{negative:,}")
    cols[4].metric("Discovery Problems", f"{discovery:,}")
    cols[5].metric("Recommendation Frustrations", f"{recommendation:,}")

    left, right = st.columns(2)

    with left:
        sentiment_counts = (
            reviews["sentiment"].value_counts().rename_axis("sentiment").reset_index(name="count")
        )
        fig = px.pie(
            sentiment_counts,
            names="sentiment",
            values="count",
            title="Sentiment Distribution",
            hole=0.35,
        )
        st.plotly_chart(fig, use_container_width=True)

    with right:
        source_counts = (
            reviews["source"].value_counts().rename_axis("source").reset_index(name="count")
        )
        bar_chart(source_counts, "source", "count", "Reviews by Source")


def pain_points_tab(reviews: pd.DataFrame, insights: pd.DataFrame) -> None:
    left, right = st.columns(2)

    with left:
        st.subheader("Top Discovery Problems")
        discovery = insight_table(insights, "discovery_problem")
        st.dataframe(discovery, use_container_width=True, hide_index=True)
        bar_chart(discovery, "label", "count", "Top Discovery Problems")
        if not discovery.empty:
            label = st.selectbox(
                "Show discovery excerpts for",
                discovery["label"].tolist(),
                key="discovery_examples",
            )
            selected_insight_examples(reviews, insights, "discovery_problem", label)

    with right:
        st.subheader("Top Recommendation Frustrations")
        frustrations = insight_table(insights, "frustration")
        st.dataframe(frustrations, use_container_width=True, hide_index=True)
        bar_chart(frustrations, "label", "count", "Top Recommendation Frustrations")
        if not frustrations.empty:
            label = st.selectbox(
                "Show recommendation excerpts for",
                frustrations["label"].tolist(),
                key="frustration_examples",
            )
            selected_insight_examples(reviews, insights, "frustration", label)


def build_segment_summary(reviews: pd.DataFrame) -> pd.DataFrame:
    rows = []
    all_segments = sorted({segment for segments in reviews["segment_list"] for segment in segments})

    for segment in all_segments:
        mask = reviews["segment_list"].apply(lambda segments: segment in segments)
        segment_reviews = reviews[mask]
        rows.append(
            {
                "Segment": segment,
                "Review Count": len(segment_reviews),
                "Discovery Problems": int(
                    (segment_reviews["theme"] == "DISCOVERY_PROBLEMS").sum()
                ),
                "Recommendation Problems": int(
                    (segment_reviews["theme"] == "RECOMMENDATION_FRUSTRATIONS").sum()
                ),
                "Discovery %": pct(
                    int((segment_reviews["theme"] == "DISCOVERY_PROBLEMS").sum()),
                    len(segment_reviews),
                ),
                "Recommendation %": pct(
                    int(
                        (
                            segment_reviews["theme"]
                            == "RECOMMENDATION_FRUSTRATIONS"
                        ).sum()
                    ),
                    len(segment_reviews),
                ),
            }
        )

    return pd.DataFrame(rows).sort_values("Review Count", ascending=False)


def render_header(reviews: pd.DataFrame) -> None:
    total = len(reviews)
    source_count = reviews["source"].nunique() if "source" in reviews else 0
    st.markdown(
        f"""
        <div class="dashboard-header">
            <div>
                <div class="eyebrow">
                    <svg class="spotify-logo" viewBox="0 0 64 64" role="img" aria-label="Spotify logo">
                        <circle cx="32" cy="32" r="30" fill="#1ed760"/>
                        <path d="M18 25c10-3 22-2 31 3" fill="none" stroke="#111" stroke-width="5" stroke-linecap="round"/>
                        <path d="M20 34c8-2 18-1 26 3" fill="none" stroke="#111" stroke-width="4" stroke-linecap="round"/>
                        <path d="M22 42c6-1 14 0 20 3" fill="none" stroke="#111" stroke-width="3" stroke-linecap="round"/>
                    </svg>
                    Spotify
                </div>
                <h1 class="hero-title">AI-Powered Review Discovery Engine</h1>
                <div class="hero-subtitle">
                    What users actually say about finding new music — synthesised from app stores,
                    community forums, and social feedback refreshed against the product questions.
                </div>
            </div>
            <div class="header-meta">
                <div><span class="status-dot"></span>Live dataset · {total:,} reviews</div>
                <div>{source_count} sources · {date_range_label(reviews)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_cards(reviews: pd.DataFrame) -> None:
    total = len(reviews)
    positive = metric_value(reviews, "sentiment", "positive")
    negative = metric_value(reviews, "sentiment", "negative")
    discovery = metric_value(reviews, "theme", "DISCOVERY_PROBLEMS")
    recommendation = metric_value(reviews, "theme", "RECOMMENDATION_FRUSTRATIONS")
    source_count = reviews["source"].nunique() if "source" in reviews else 0

    cards = [
        metric_card(
            "Total Reviews",
            f"{total:,}",
            f"across {source_count} sources",
            bars=[5, 8, 6, 11, 7, 13, 9, 14, 10, 12],
        ),
        metric_card(
            "Positive Sentiment",
            f"{pct(positive, total)}%",
            f"{positive:,} reviews · {pct(negative, total)}% negative",
            "teal",
            bars=[4, 6, 5, 8, 6, 10, 7, 11, 8, 12],
        ),
        metric_card(
            "Discovery Complaint Rate",
            f"{pct(discovery, total)}%",
            "cite discovery problems",
            "red",
            bars=[3, 7, 5, 8, 6, 11, 8, 13, 7, 9],
        ),
        metric_card(
            "Recommendation Complaint Rate",
            f"{pct(recommendation, total)}%",
            "cite recommendation frustrations",
            "red",
            bars=[4, 8, 6, 7, 5, 10, 6, 9, 5, 7],
        ),
    ]

    cols = st.columns(4)
    for col, card in zip(cols, cards):
        col.markdown(card, unsafe_allow_html=True)


def render_theme_frequency(reviews: pd.DataFrame) -> None:
    counts = reviews["theme"].value_counts().to_dict()
    rows = [(theme, counts.get(theme, 0)) for theme in THEME_ORDER]
    max_count = max([count for _, count in rows] or [1]) or 1
    content = section_title(
        "Theme Frequency",
        "Q1, Q2, Q3, Q4, Q6 — why discovery breaks down",
    )

    for theme, count in rows:
        width = 8 if count == 0 else max(10, int((count / max_count) * 100))
        content += (
            "<div class='theme-row'>"
            f"<div class='theme-name'>{escape(theme_label(theme))}</div>"
            "<div class='bar-track'>"
            f"<div class='bar-fill' style='width:{width}%;background:{THEME_COLORS[theme]}'></div>"
            "</div>"
            f"<div class='bar-count'>{count:,}</div>"
            "</div>"
        )

    st.markdown(f"<div class='panel'>{content}</div>", unsafe_allow_html=True)


def render_segment_snapshot(reviews: pd.DataFrame) -> None:
    segment_summary = build_segment_summary(reviews).head(5)
    content = section_title("Segment Snapshot", "Q5 — who struggles most")
    content += (
        "<table class='segment-table'>"
        "<thead><tr>"
        "<th>Segment</th><th>Discovery<br/>Problems</th><th>Recommendation<br/>Frustrations</th>"
        "</tr></thead><tbody>"
    )

    for _, row in segment_summary.iterrows():
        discovery_pct = int(row["Discovery %"])
        recommendation_pct = int(row["Recommendation %"])
        content += (
            "<tr>"
            f"<td><div class='segment-name'>{escape(str(row['Segment']))}</div>"
            f"<div class='meta-text'>{int(row['Review Count']):,} reviews</div></td>"
            "<td><div class='mini-metric'>"
            "<div class='mini-track'>"
            f"<div class='mini-fill' style='width:{discovery_pct}%;background:var(--accent)'></div>"
            "</div>"
            f"<span>{discovery_pct}%</span>"
            "</div></td>"
            "<td><div class='mini-metric'>"
            "<div class='mini-track'>"
            f"<div class='mini-fill' style='width:{recommendation_pct}%;background:var(--red)'></div>"
            "</div>"
            f"<span>{recommendation_pct}%</span>"
            "</div></td>"
            "</tr>"
        )

    content += "</tbody></table>"
    st.markdown(f"<div class='panel'>{content}</div>", unsafe_allow_html=True)


def first_example_quote(
    reviews: pd.DataFrame, insights: pd.DataFrame, insight_type: str, label: str
) -> str:
    row = insights[
        (insights["insight_type"] == insight_type) & (insights["label"] == label)
    ]
    if row.empty:
        return ""
    example_ids = parse_example_ids(row.iloc[0]["example_ids"])
    if not example_ids:
        return ""
    example = reviews[reviews["id"].isin(example_ids)]
    if example.empty:
        return ""
    return " ".join(str(example.iloc[0]["clean_text"]).split())


def render_opportunities(reviews: pd.DataFrame, insights: pd.DataFrame) -> None:
    opportunities = insight_table(insights, "opportunity", 10)
    if opportunities.empty:
        opportunities = insight_table(insights, "discovery_problem", 10)

    content = section_title(
        "Top 10 Product Opportunities",
        "Q6 — ranked by supporting review volume",
    )

    for index, row in opportunities.iterrows():
        label = str(row["label"])
        summary = truncate_text(str(row.get("summary", "")), 230)
        quote = first_example_quote(reviews, insights, "opportunity", label)
        quote_html = (
            f"<div class='quote'>&ldquo;{escape(quote)}&rdquo;</div>"
            if quote
            else ""
        )
        content += (
            "<div class='opportunity-row'>"
            f"<div class='rank'>{index + 1:02d}</div>"
            "<div>"
            f"<div class='opportunity-title'>{escape(label)}</div>"
            f"<div class='opportunity-summary'>{escape(summary)}</div>"
            f"{quote_html}"
            "</div>"
            f"<div class='mention-count'>{int(row['count']):,} mentions</div>"
            "</div>"
        )

    st.markdown(f"<div class='opportunities-panel'>{content}</div>", unsafe_allow_html=True)


def render_review_explorer(reviews: pd.DataFrame) -> None:
    st.markdown(
        "<div class='explorer-panel'>"
        + section_title("Review Explorer", "filter · search · sort by date for basic trend reading")
        + "</div>",
        unsafe_allow_html=True,
    )

    filter_cols = st.columns([1.2, 1, 1, 2.5])
    theme_options = ["All themes"] + [theme_label(theme) for theme in THEME_ORDER]
    selected_theme_label = filter_cols[0].selectbox("Theme", theme_options)

    source_options = ["All sources"] + sorted(
        {source_label(source) for source in reviews["source"].dropna().unique()}
    )
    selected_source_label = filter_cols[1].selectbox("Source", source_options)

    sentiment_options = ["All sentiment"] + sorted(
        reviews["sentiment"].dropna().unique().tolist()
    )
    selected_sentiment = filter_cols[2].selectbox("Sentiment", sentiment_options)
    search_text = filter_cols[3].text_input("Search", placeholder="Search review text...")

    filtered = reviews.copy()
    if selected_theme_label != "All themes":
        selected_theme = next(
            (theme for theme in THEME_ORDER if theme_label(theme) == selected_theme_label),
            None,
        )
        if selected_theme:
            filtered = filtered[filtered["theme"] == selected_theme]
    if selected_source_label != "All sources":
        filtered = filtered[filtered["source"].apply(source_label) == selected_source_label]
    if selected_sentiment != "All sentiment":
        filtered = filtered[filtered["sentiment"] == selected_sentiment]
    if search_text.strip():
        filtered = filtered[
            filtered["clean_text"].str.contains(search_text.strip(), case=False, na=False)
        ]

    display = filtered.head(250).copy()
    display["Date"] = display["date"].dt.strftime("%Y-%m-%d")
    display["Source"] = display["source"].apply(source_label)
    display["Theme"] = display["theme"].apply(theme_label)
    display["Sentiment"] = display["sentiment"].str.title()
    display["Review"] = display["clean_text"].apply(lambda value: truncate_text(value, 170))

    st.caption(f"Showing {len(display):,} of {len(reviews):,} reviews")
    st.dataframe(
        display[["Date", "Source", "Theme", "Sentiment", "Review"]],
        use_container_width=True,
        hide_index=True,
        height=360,
    )


def editorial_dashboard(reviews: pd.DataFrame, insights: pd.DataFrame) -> None:
    render_header(reviews)
    render_metric_cards(reviews)
    st.markdown("<div style='height:1.1rem'></div>", unsafe_allow_html=True)

    left, right = st.columns([1.35, 1])
    with left:
        render_theme_frequency(reviews)
    with right:
        render_segment_snapshot(reviews)

    render_opportunities(reviews, insights)
    render_review_explorer(reviews)


def segments_tab(reviews: pd.DataFrame, insights: pd.DataFrame) -> None:
    st.subheader("Listening Goals")
    listening_goals = insight_table(insights, "listening_goal")
    st.dataframe(listening_goals, use_container_width=True, hide_index=True)
    bar_chart(listening_goals, "label", "count", "Listening Goals")

    st.subheader("User Segment Summary")
    segment_summary = build_segment_summary(reviews)
    st.dataframe(segment_summary, use_container_width=True, hide_index=True)

    chart_df = segment_summary.melt(
        id_vars="Segment",
        value_vars=["Discovery Problems", "Recommendation Problems"],
        var_name="Problem Type",
        value_name="Reviews",
    )
    if not chart_df.empty:
        fig = px.bar(
            chart_df,
            x="Segment",
            y="Reviews",
            color="Problem Type",
            barmode="group",
            title="Problems by User Segment",
        )
        st.plotly_chart(fig, use_container_width=True)


def filter_reviews(reviews: pd.DataFrame) -> pd.DataFrame:
    filtered = reviews.copy()

    with st.sidebar:
        st.header("Review Explorer Filters")

        sources = sorted(filtered["source"].dropna().unique().tolist())
        selected_sources = st.multiselect("Source", sources, default=sources)
        if selected_sources:
            filtered = filtered[filtered["source"].isin(selected_sources)]

        sentiments = sorted(filtered["sentiment"].dropna().unique().tolist())
        selected_sentiments = st.multiselect("Sentiment", sentiments, default=sentiments)
        if selected_sentiments:
            filtered = filtered[filtered["sentiment"].isin(selected_sentiments)]

        themes = sorted(filtered["theme"].dropna().unique().tolist())
        selected_themes = st.multiselect("Theme", themes, default=themes)
        if selected_themes:
            filtered = filtered[filtered["theme"].isin(selected_themes)]

        topics = sorted(filtered["topic_label"].dropna().unique().tolist())
        selected_topics = st.multiselect("Topic", topics)
        if selected_topics:
            filtered = filtered[filtered["topic_label"].isin(selected_topics)]

        segments = sorted({segment for row in filtered["segment_list"] for segment in row})
        selected_segments = st.multiselect("Segment", segments)
        if selected_segments:
            filtered = filtered[
                filtered["segment_list"].apply(
                    lambda row: any(segment in row for segment in selected_segments)
                )
            ]

        valid_dates = filtered["date"].dropna()
        if not valid_dates.empty:
            min_date = valid_dates.min().date()
            max_date = valid_dates.max().date()
            selected_range = st.date_input("Date", value=(min_date, max_date))
            if isinstance(selected_range, tuple) and len(selected_range) == 2:
                start, end = selected_range
                filtered = filtered[
                    (filtered["date"].dt.date >= start) & (filtered["date"].dt.date <= end)
                ]

    return filtered


def opportunities_and_explorer_tab(reviews: pd.DataFrame, insights: pd.DataFrame) -> None:
    st.subheader("Top Opportunities")
    opportunities = insight_table(insights, "opportunity")
    st.dataframe(opportunities, use_container_width=True, hide_index=True)
    bar_chart(opportunities, "label", "count", "Top Opportunities")

    if not opportunities.empty:
        label = st.selectbox(
            "Show opportunity excerpts for",
            opportunities["label"].tolist(),
            key="opportunity_examples",
        )
        selected_insight_examples(reviews, insights, "opportunity", label)

    st.divider()
    st.subheader("Review Explorer")
    filtered = filter_reviews(reviews)

    display_cols = [
        "id",
        "source",
        "date",
        "sentiment",
        "theme",
        "topic_label",
        "segment_text",
        "rating",
    ]
    st.caption(f"Showing {len(filtered):,} of {len(reviews):,} enriched reviews")
    st.dataframe(
        filtered[display_cols],
        use_container_width=True,
        hide_index=True,
    )

    if filtered.empty:
        return

    selected_id = st.selectbox(
        "Open full review",
        filtered["id"].tolist(),
        format_func=lambda review_id: f"{review_id} | {filtered.loc[filtered['id'] == review_id, 'source'].iloc[0]}",
    )
    selected = filtered[filtered["id"] == selected_id].iloc[0]
    st.markdown("#### Full Review")
    st.write(selected["clean_text"])
    st.caption(
        f"Source: {selected['source']} | Date: {selected['date']} | "
        f"Sentiment: {selected['sentiment']} | Theme: {selected['theme']} | "
        f"Topic: {selected['topic_label']} | Segment: {selected['segment_text']}"
    )
    if selected.get("url"):
        st.link_button("Open source", selected["url"])


def main() -> None:
    inject_styles()

    if not DB_PATH.exists():
        st.error("Database not found. Run `python run_all.py --phase 1` first.")
        return

    db_mtime = _db_mtime()
    reviews = load_reviews(db_mtime)
    insights = load_insights(db_mtime)

    if reviews.empty:
        st.warning("No enriched reviews found. Run phases 1-4 before launching the dashboard.")
        return

    if insights.empty:
        st.warning("No insights found. Run `python run_all.py --phase 4` for top insight tables.")

    editorial_dashboard(reviews, insights)


if __name__ == "__main__":
    main()
