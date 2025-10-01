# University of Leeds Lecturer AI‑Skill Scraper

---

## 📖 Table of Contents

1. [Project Overview](#project-overview)
2. [Key Features](#key-features)
3. [Repository Layout](#repository-layout)
4. [Quick Start](#quick-start)
5. [Configuration](#configuration)
6. [Running the Tools](#running-the-tools)
   - [CLI](#cli-usage)
   - [Desktop GUI](#desktop-gui)
7. [Data Model](#data-model)
8. [Extending the Project](#extending-the-project)
9. [Troubleshooting & FAQ](#troubleshooting--faq)
10. [Roadmap](#roadmap)
11. [Acknowledgements & License](#acknowledgements--license)

---

## Project Overview

This project automates the discovery of Leeds lecturers who publish—or appear to have expertise—in Artificial Intelligence. It **scrapes**:

- **University of Leeds staff pages** to collect lecturer names, positions, expertise, profile URLs and *optional* Google Scholar links.
- **Google Scholar** to find each lecturer’s profile, publication titles and declared interests.

All data are stored in **MongoDB**, and the text of interests / publications is passed through a two‑stage *zero‑shot* classifier (Meta’s `facebook/bart-large-mnli`) + KeyBERT key‑phrase extraction to determine AI‑relevance.

A **PyQt5 desktop application** offers a point‑and‑click interface on top of the same codebase, while a simple **command‑line interface** is available for servers or scheduled runs.

---

## Key Features

| Area                   | Highlights                                                                                                                                                       |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Scraping**           | Rotating proxies & headers, Google CAPTCHA detection, pagination handling for Scholar publications.                                                              |
| **AI Skill Detection** | 2‑stage zero‑shot classification ("Artificial Intelligence" ↑) plus fine‑grained negative labels; KeyBERT key‑phrase extraction; duplicate phrase pruning.       |
| **Database**           | MongoDB upsert; easy re‑scrape (force‑update) flags; a single `lecturers` collection holds everything.                                                           |
| **Interface**          | *CLI* workflow for automation; *GUI* (PyQt5) with background worker threads so windows never freeze; rich filters (school, AI‑only, skill search, AND/OR logic). |
| **Extensibility**      | School URLs live in one dictionary (`department.py`); classifier labels & thresholds tunable in `ai_classifiers.py`.                                             |

---

## Repository Layout

```
├── ai_classifiers.py   # Zero‑shot + KeyBERT utilities
├── department.py       # Mapping of Leeds schools → faculty → staff‑list URL
├── database.py         # MongoDB connection helper
├── interface.py        # PyQt5 desktop app
├── main.py             # CLI entry‑point (menu)
├── requirements.txt    # Python dependencies
├── scraper.py          # Leeds staff‑page scraper
├── scholar_scraper.py  # Google Scholar scraper
└── utils.py            # Shared helpers (proxy rotation, text utils…)
```

---

## Quick Start

### 1 · Prerequisites

- Python ≥ 3.10 (tested on 3.11)
- A MongoDB instance (Atlas or local). The default URI **must be changed**—see § [Configuration](#configuration).
- Chrome/Firefox (only for your own browsing; scraping uses `requests`).

### 2 · Clone & Install

```bash
# 0) clone
$ git clone https://github.com/jsv832/UoL-Expert-Finder.git
$ cd leeds-ai-scraper

# 1) create and activate a virtual environment (recommended)
$ python -m venv .venv
$ source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2) install Python deps
$ pip install -r requirements.txt

# 3) download SpaCy model (first run only)
$ python -m spacy download en_core_web_sm
```

---


> **⚠️ Security note**: `database.py` currently contains a hard‑coded `MONGO_URI`.
> It should be moved to environment variable but to make it easier to have access to project it visible

---

## Running the Tools

### CLI Usage

Run the menu‑driven CLI:

```bash
$ python main.py
```

You’ll be asked to:

1. **Scrape Leeds staff pages** (`scraper.py`).
2. **Scrape Google Scholar** (`scholar_scraper.py`).
3. **Run both in sequence** .

Each scraper can optionally **force‑update** existing lecturer documents (otherwise they are skipped if already processed).

### Desktop GUI

```bash
$ python interface.py
```

The window offers three tabs:

- **Run Scrapers** – choose school, force‑update, background progress.
- **Professor List** – browse, filter by school/name/AI‑only, double‑click to see full details.
- **Skill Search** – build an AND/OR query of AI skill keywords to find matching lecturers.



## Data Model

All documents reside in collection ``; key fields include:

| Field                   | Type       | Description                                     |
| ----------------------- | ---------- | ----------------------------------------------- |
| `_id`                   | String     |  Primary key; the lecturer’s staff‑profile URL. |
| `name`                  | String     | Lecturer’s full name.                           |
| `school` / `department` | String     | University of Leeds organisational units.       |
| `skills_expertise`      | List[str]  | Staff page “Areas of expertise”.                |
| `research_papers`       | List[dict] | Publications scraped from Leeds pages.          |
| `scholar_profile`       | String     | Google Scholar URL (if found).                  |
| `scholar_publications`  | List[dict] | All Scholar publications (title + year).        |
| `ai_skills`             | List[str]  | **Final deduplicated AI‑skill key‑phrases**.    |
| `is_ai_lecturer`        | Bool       | True if any AI skills were detected.            |
| `scholar_processed`     | Bool       | Flag to avoid re‑processing.                    |

---

## Extending the Project

- **Add new schools** – Edit `department.py`.
- **Add Scripts** – Edit `utils.py`.
- **Tweak AI detection** – Adjust thresholds/constants in `ai_classifiers.py`.
- **Improve AI classifier** - Fine Tune model instead of zero-shot `ai_classifiers.py`/
- **Headless scraping** – Integrate Selenium/Playwright if JavaScript‑rendered pages require it.

## Troubleshooting & FAQ

| Problem                              | Solution                                                                                  |
| ------------------------------------ | ----------------------------------------------------------------------------------------- |
| *Google scholar blocks with CAPTCHA* | Wait, change IP/proxy, lower request rate (`utils.select_proxy_and_headers`).             |
| *GUI freezes*                        | Long scrapes run inside `ScrapeWorker` threads; ensure PyQt ≥ 5.15.                       |
| *Empty AI‑skills*                    | Check `AI_RELATED_THRESHOLD` (default 0.60); raise/lower to tune recall.                  |
| *Duplicate lecturers*                | The `_id` is the Leeds profile URL – duplicates shouldn’t appear unless the site changes. |


## Acknowledgements & License

This project bundles open‑source work, notably:

- **SpaCy** (MIT), **Transformers** (Apache‑2.0), **KeyBERT** (Apache‑2.0)
- *facebook/bart-large-mnli* model © Meta AI
- University of Leeds staff pages and Google Scholar © their respective owners.
