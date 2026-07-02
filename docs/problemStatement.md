# AI-Powered Review Discovery Engine

## Problem

Spotify has millions of users and one of the world's most advanced recommendation systems. Even so, a large share of listening still comes from repeat playlists, familiar artists, and previously discovered tracks.

The Growth Team's strategic goal is to **increase meaningful music discovery** and **reduce repetitive listening**. Product decisions need to be grounded in what users actually say—not only in aggregate metrics.

Today, feedback is scattered across app stores, Reddit, forums, and social platforms. There is no single workflow to collect, clean, classify, and explore that voice at scale.

---

## Objective

Build an end-to-end **review intelligence system** that ingests recent user feedback, turns it into structured insights, and surfaces them in a dashboard a Product Manager can use without manually reading thousands of posts.

---

## Scope

### 1. Data import (last ~90 days)

Collect reviews and discussions from:

| Source | Notes |
|--------|--------|
| App Store | iOS reviews |
| Play Store | Android reviews |
| Spotify Community forums | Forum threads from Ideas and Issues boards |
| Community forums | e.g. Spotify Community |
| Social media | Public conversations where available |

**Time window:** Import content from roughly the **last 90 days** only. Use each platform's publish or post date to enforce the cutoff.

**Per-record metadata** (required for traceability and filtering):

- Platform / source
- Date
- Rating (when available)
- Original URL or platform ID

---

### 2. Data cleaning

Run a standardized pipeline on raw ingested data. Store cleaned output separately from raw data.

| Step | Action |
|------|--------|
| Deduplication | Remove duplicates within and across sources |
| URL removal | Strip URLs from review text |
| Emoji removal | Remove emojis |
| Stopword removal | Remove common stopwords |
| Normalization | Lowercase, trim whitespace, standardize punctuation |
| Language detection | Detect review language |
| Language filter | Retain **English-only** reviews |

---

### 3. Topic modeling

Discover themes automatically from cleaned text. Assign each review a **topic label** and **confidence score**.

Expected topic areas (the model may surface additional ones):

- Music Discovery
- Recommendations
- Search
- Playlists
- Artist Exploration
- Personalization
- Algorithm Quality
- Repetitive Content
- User Interface

---

### 4. Theme classification

Map reviews into business themes aligned with core product questions. A review may relate to multiple topics; assign the primary business theme with supporting topic tags.

| Theme | Product question |
|-------|------------------|
| `DISCOVERY_PROBLEMS` | Why do users struggle to discover new music? |
| `RECOMMENDATION_FRUSTRATIONS` | What frustrates users about recommendations? |
| `LISTENING_GOALS` | What listening behaviors are users trying to achieve? |
| `REPEAT_LISTENING_CAUSES` | What causes repeat listening? |
| `UNMET_NEEDS` | What opportunities emerge from user feedback? |

**Example**

> *"Spotify keeps recommending songs I already know."*
>
> - Theme: `RECOMMENDATION_FRUSTRATIONS`
> - Related topics: Recommendations, Repetitive Content, Algorithm Quality

---

### 5. User segmentation

Infer segments from review text and context (e.g. mentions of Premium, playlists, podcasts). A review may map to one or more segments with a confidence score.

Candidate segments:

- New Users
- Premium Users
- Free Users
- Power Users
- Playlist Users
- Genre Explorers
- Podcast Listeners
- Casual Listeners

---

### 6. Insight extraction

Produce structured insights across six dimensions, backed by frequency counts, representative excerpts, and sentiment where applicable:

1. **Discovery challenges** — barriers to finding new music
2. **Recommendation issues** — complaints about the recommendation engine
3. **Listening intentions** — goals users express in feedback
4. **Repeat listening causes** — why users stick to familiar content
5. **User segments** — which groups face which problems
6. **Unmet needs** — recurring gaps and feature opportunities

---

## Product questions to answer

| # | Question |
|---|----------|
| 1 | Why do users struggle to discover new music? |
| 2 | What are the most common frustrations with recommendations? |
| 3 | What listening behaviors are users trying to achieve? |
| 4 | What causes users to repeatedly listen to the same content? |
| 5 | Which user segments experience different discovery challenges? |
| 6 | What unmet needs emerge consistently across reviews? |

---

## Dashboard

A single dashboard should let a PM move from overview to drill-down without leaving the app.

### Overview

**Metrics**

- Total reviews analyzed
- Positive / neutral / negative review counts
- Discovery problem reviews
- Recommendation frustration reviews

**Charts**

- Sentiment distribution (pie)
- Reviews by source (bar)

### Top user pain points

Answers questions 1 and 2.

**Tables**

Discovery problems and recommendation frustrations, each with problem/frustration name and count (e.g. "Hard to find new artists — 120", "Repetitive recommendations — 180").

**Charts**

- Bar chart: top discovery problems
- Bar chart: top recommendation frustrations

**Include** 3–5 representative review excerpts per category.

### User segments & listening behavior

Answers questions 3 and 5.

**Listening goals** — counts for goals such as:

- Finding new artists
- Exploring genres
- Discovering playlists
- Mood-based listening

**Segment summary**

| Segment | Review count | Discovery problems | Recommendation problems |
|---------|--------------|--------------------|-------------------------|
| New Users | | | |
| Premium Users | | | |
| Free Users | | | |
| Playlist Users | | | |

**Charts**

- Bar chart: listening goals
- Bar chart: problems by user segment

### Opportunities & review explorer

Answers question 6.

**Top opportunities** — ranked list with supporting review counts (e.g. "Better genre exploration — 85").

**Review explorer** — interactive table of individual reviews.

**Filters:** topic, theme, sentiment, segment, date, source.

Row click opens full review text and metadata.

---

## Success criteria

The system is successful when a Product Manager can:

- See the scale and sentiment of user feedback at a glance
- Understand top discovery problems and recommendation frustrations, with supporting excerpts
- Compare listening goals and pain points across user segments
- Identify actionable opportunities backed by real user voice
- Explore individual reviews through a filterable Review Explorer

All of the above should be achievable from one dashboard—without manually reviewing thousands of individual posts.
