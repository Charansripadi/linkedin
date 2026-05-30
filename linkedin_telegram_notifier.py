"""
LinkedIn Job Scraper → Telegram Notifier
Personalised for: Sri Charan Sripadi
No browser/Selenium needed — uses requests only.
"""

import os
import time
import json
import hashlib
import logging
import schedule
import requests
from datetime import datetime
from bs4 import BeautifulSoup

# ─────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8669817974:AAForaxhZoXmaXfWoFUkKSWZuEaH_MvPLfc")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "@lin_lin_78658bot")

LINKEDIN_EMAIL    = "sricharansripadi618@gmail.com"
LINKEDIN_PASSWORD = os.environ.get("LINKEDIN_PASSWORD", "ssrings90")

JOB_SEARCHES = [
    # ML / AI — UK
    {"keywords": "ML Engineer Computer Vision",        "location": "United Kingdom"},
    {"keywords": "Machine Learning Engineer PyTorch",  "location": "United Kingdom"},
    {"keywords": "Computer Vision Engineer",           "location": "United Kingdom"},
    {"keywords": "AI Engineer Python",                 "location": "United Kingdom"},
    {"keywords": "Deep Learning Engineer",             "location": "United Kingdom"},
    {"keywords": "Research Engineer AI",               "location": "United Kingdom"},
    # SDE — UK
    {"keywords": "Software Engineer Python",           "location": "United Kingdom"},
    {"keywords": "Backend Engineer Python",            "location": "United Kingdom"},
    {"keywords": "Software Developer AI ML",           "location": "United Kingdom"},
    {"keywords": "Graduate Software Engineer",         "location": "United Kingdom"},
    # Europe / Remote
    {"keywords": "ML Engineer Computer Vision",        "location": "Netherlands"},
    {"keywords": "Machine Learning Engineer",          "location": "Ireland"},
    {"keywords": "Software Engineer Python remote",    "location": ""},
    {"keywords": "ML Engineer remote",                 "location": ""},
]

TITLE_KEYWORDS = [
    "machine learning", "ml ", "computer vision", "deep learning",
    "ai engineer", "artificial intelligence", "research engineer",
    "software engineer", "software developer", "backend engineer",
    "sde", "python engineer", "data scientist",
]

SPONSORSHIP_SIGNALS = [
    "visa sponsorship", "sponsor", "skilled worker", "tier 2",
    "work permit", "relocation", "visa support", "right to work",
    "international candidates", "global talent",
]

CHECK_INTERVAL_MINUTES = 60
MAX_JOBS_PER_SEARCH    = 20
SEEN_JOBS_FILE         = "seen_jobs.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Seen jobs ──────────────────────────────────────────────────────────────────

def load_seen():
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(list(seen), f)

def job_id(url):
    return hashlib.md5(url.encode()).hexdigest()


# ── Telegram ───────────────────────────────────────────────────────────────────

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }, timeout=10)
        r.raise_for_status()
        log.info("Telegram message sent.")
    except Exception as e:
        log.error(f"Telegram failed: {e}")

def format_message(job):
    sponsorship = "✅ Mentions sponsorship/relocation" if job.get("has_sponsorship") else "⚠️ Check description"
    return (
        f"🚀 <b>New Job Found!</b>\n\n"
        f"💼 <b>{job['title']}</b>\n"
        f"🏢 {job['company']}\n"
        f"📍 {job['location']}\n"
        f"🛂 {sponsorship}\n"
        f"🔗 Apply type: <b>{job['apply_type']}</b>\n\n"
        f"🌐 <a href=\"{job['url']}\">View on LinkedIn</a>"
    )

def send_startup():
    send_telegram(
        "✅ <b>LinkedIn Notifier Started</b>\n\n"
        f"👤 Sri Charan Sripadi\n"
        f"🔍 {len(JOB_SEARCHES)} searches active\n"
        f"⏱ Checking every {CHECK_INTERVAL_MINUTES} min\n\n"
        "Sending jobs with <b>external apply links</b> + sponsorship signals."
    )


# ── LinkedIn scraper (no browser) ─────────────────────────────────────────────

def search_jobs(keywords, location):
    """Scrape LinkedIn public job search (no login needed)."""
    params = {
        "keywords": keywords,
        "location": location,
        "f_AL": "false",   # include non-Easy Apply
        "sortBy": "DD",
        "start": 0,
    }
    url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            log.warning(f"Search returned {r.status_code} for '{keywords}'")
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.find_all("li")[:MAX_JOBS_PER_SEARCH]
        jobs = []
        for card in cards:
            try:
                title_el   = card.find("h3", class_="base-search-card__title")
                company_el = card.find("h4", class_="base-search-card__subtitle")
                loc_el     = card.find("span", class_="job-search-card__location")
                link_el    = card.find("a", class_="base-card__full-link")

                if not title_el or not link_el:
                    continue

                title = title_el.get_text(strip=True)
                if not any(kw in title.lower() for kw in TITLE_KEYWORDS):
                    continue

                jobs.append({
                    "title":    title,
                    "company":  company_el.get_text(strip=True) if company_el else "Unknown",
                    "location": loc_el.get_text(strip=True) if loc_el else location,
                    "url":      link_el["href"].split("?")[0],
                })
            except Exception as e:
                log.debug(f"Card error: {e}")
        log.info(f"  '{keywords}' → {len(jobs)} relevant jobs")
        return jobs
    except Exception as e:
        log.error(f"Search error: {e}")
        return []


def check_job_details(job):
    """
    Fetch job detail page.
    Returns (apply_type, has_sponsorship, apply_url)
    apply_type: 'external' | 'easy_apply' | 'unknown'
    """
    try:
        r = requests.get(job["url"], headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        page_text = soup.get_text().lower()

        # Check sponsorship signals
        has_sponsorship = any(sig in page_text for sig in SPONSORSHIP_SIGNALS)

        # Detect apply type
        apply_btn = soup.find("a", class_="apply-button") or \
                    soup.find("a", {"data-tracking-control-name": lambda x: x and "offsite" in x}) or \
                    soup.find("a", string=lambda x: x and "apply" in x.lower())

        easy_apply = soup.find("span", string=lambda x: x and "easy apply" in x.lower()) or \
                     "easy apply" in page_text[:2000]

        if easy_apply and not apply_btn:
            return "easy_apply", has_sponsorship, None

        if apply_btn and apply_btn.get("href"):
            href = apply_btn["href"]
            if "linkedin.com" not in href and href.startswith("http"):
                return "external", has_sponsorship, href

        # Fallback — check all links for external apply
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if ("apply" in href.lower() and
                    "linkedin.com" not in href and
                    href.startswith("http")):
                return "external", has_sponsorship, href

        return "unknown", has_sponsorship, None

    except Exception as e:
        log.debug(f"Detail error for {job['url']}: {e}")
        return "unknown", False, None


# ── Main ───────────────────────────────────────────────────────────────────────

def run_check():
    log.info(f"=== Check at {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")
    seen = load_seen()
    new_count = 0

    for search in JOB_SEARCHES:
        jobs = search_jobs(search["keywords"], search["location"])
        for job in jobs:
            jid = job_id(job["url"])
            if jid in seen:
                continue
            seen.add(jid)

            apply_type, has_sponsorship, apply_url = check_job_details(job)

            # Only notify for external apply jobs
            if apply_type == "external":
                job["apply_type"] = "External Apply 🌐"
                job["has_sponsorship"] = has_sponsorship
                if apply_url:
                    job["url"] = apply_url
                log.info(f"✅ {job['title']} @ {job['company']} — sponsorship={has_sponsorship}")
                send_telegram(format_message(job))
                new_count += 1
                time.sleep(1)

            time.sleep(1)
        time.sleep(2)

    save_seen(seen)
    log.info(f"Done — {new_count} new job(s) sent.")


if __name__ == "__main__":
    log.info("Starting LinkedIn → Telegram Notifier")
    send_startup()
    run_check()
    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(run_check)
    while True:
        schedule.run_pending()
        time.sleep(30)
