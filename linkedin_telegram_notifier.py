"""
LinkedIn Job Scraper → Telegram Notifier
Personalised for: Sri Charan Sripadi
Profile: ML Engineer | Computer Vision | Python/PyTorch | UK (Visa Sponsorship Welcome)

SETUP:
1. pip install requests beautifulsoup4 selenium webdriver-manager schedule
2. Fill in your Telegram + LinkedIn credentials below
3. Run: python linkedin_telegram_notifier.py
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
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ─────────────────────────────────────────
#  YOUR CONFIG — fill these in
# ─────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8669817974:AAForaxhZoXmaXfWoFUkKSWZuEaH_MvPLfc")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "@lin_lin_78658bot")

LINKEDIN_EMAIL    = "sricharansripadi618@gmail.com"
LINKEDIN_PASSWORD = os.environ.get("LINKEDIN_PASSWORD", "ssrings90")

# ── Personalised job searches — visa sponsorship welcome ────────────────────
JOB_SEARCHES = [
    # ── ML / AI roles — UK ──────────────────────────────────────────────────
    {"keywords": "ML Engineer Computer Vision visa sponsorship",       "location": "United Kingdom"},
    {"keywords": "Machine Learning Engineer PyTorch sponsorship",      "location": "United Kingdom"},
    {"keywords": "Computer Vision Engineer visa sponsor",              "location": "United Kingdom"},
    {"keywords": "AI Engineer Python sponsorship",                     "location": "United Kingdom"},
    {"keywords": "Deep Learning Engineer visa sponsorship",            "location": "Cambridge, England"},
    {"keywords": "ML Engineer Image Processing sponsor",               "location": "United Kingdom"},
    {"keywords": "Research Engineer AI visa sponsorship",              "location": "United Kingdom"},
    {"keywords": "AI Engineer Graduate visa sponsor",                  "location": "United Kingdom"},
    # ── SDE / Software Engineering roles — UK ───────────────────────────────
    {"keywords": "Software Engineer Python visa sponsorship",          "location": "United Kingdom"},
    {"keywords": "Software Developer Python visa sponsor",             "location": "United Kingdom"},
    {"keywords": "Backend Engineer Python sponsorship",                "location": "United Kingdom"},
    {"keywords": "SDE Python PyTorch visa sponsorship",                "location": "United Kingdom"},
    {"keywords": "Software Engineer AI ML visa sponsorship",           "location": "United Kingdom"},
    {"keywords": "Graduate Software Engineer visa sponsor",            "location": "United Kingdom"},
    # ── ML / AI roles — Europe & Remote ─────────────────────────────────────
    {"keywords": "Machine Learning Engineer visa sponsorship",         "location": "Netherlands"},
    {"keywords": "ML Engineer Computer Vision relocation",             "location": "Germany"},
    {"keywords": "Computer Vision Engineer sponsorship",               "location": "Ireland"},
    {"keywords": "ML Engineer Computer Vision remote visa sponsor",    "location": ""},
    {"keywords": "Deep Learning Engineer remote sponsorship",          "location": ""},
    # ── SDE roles — Europe & Remote ──────────────────────────────────────────
    {"keywords": "Software Engineer Python visa sponsorship",          "location": "Netherlands"},
    {"keywords": "Backend Engineer Python relocation sponsorship",     "location": "Germany"},
    {"keywords": "Software Engineer AI remote visa sponsor",           "location": ""},
]

# ── Sponsorship signal words — job description must hint at sponsorship ──────
# These are checked in the job detail page text.
# If REQUIRE_SPONSORSHIP_SIGNAL = True, only jobs mentioning these words are sent.
REQUIRE_SPONSORSHIP_SIGNAL = True
SPONSORSHIP_SIGNALS = [
    "visa sponsorship", "sponsor", "skilled worker visa",
    "tier 2", "work permit", "relocation", "visa support",
    "international candidates", "right to work provided",
]

# ── Filters — only notify if job title contains one of these ────────────────
TITLE_KEYWORDS_REQUIRED = [
    # ML / AI
    "machine learning", "ml ", "computer vision", "deep learning",
    "ai engineer", "artificial intelligence", "data scientist",
    "image processing", "nlp engineer", "research engineer",
    # SDE / Software Engineering
    "software engineer", "software developer", "backend engineer",
    "sde", "full stack", "fullstack", "python engineer",
    "platform engineer", "systems engineer",
]

# ── Skip jobs from these companies (optional) ───────────────────────────────
BLOCKED_COMPANIES = []

CHECK_INTERVAL_MINUTES = 60
MAX_JOBS_PER_SEARCH    = 30
SEEN_JOBS_FILE         = "seen_jobs.json"
# ─────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ── Seen-jobs tracker ──────────────────────────────────────────────────────────

def load_seen() -> set:
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(seen: set):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(list(seen), f)

def job_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()

def title_is_relevant(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in TITLE_KEYWORDS_REQUIRED)


# ── Telegram ───────────────────────────────────────────────────────────────────

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        log.info("Telegram message sent.")
    except Exception as e:
        log.error(f"Telegram send failed: {e}")

def format_job_message(job: dict) -> str:
    return (
        f"🚀 <b>Sponsored Job Found!</b>\n\n"
        f"💼 <b>{job['title']}</b>\n"
        f"🏢 {job['company']}\n"
        f"📍 {job['location']}\n"
        f"🛂 Mentions visa sponsorship / relocation\n"
        f"🕐 Posted: {job.get('posted', 'N/A')}\n\n"
        f"🌐 <a href=\"{job['apply_url']}\">Apply Externally →</a>\n"
        f"🔎 <a href=\"{job['linkedin_url']}\">View on LinkedIn</a>\n\n"
        f"<i>Matched search: {job.get('search_kw', '')}</i>"
    )

def send_startup_message():
    msg = (
        "✅ <b>LinkedIn → Telegram Notifier Started</b>\n\n"
        f"👤 Sri Charan Sripadi\n"
        f"🔍 Watching {len(JOB_SEARCHES)} job searches\n"
        f"⏱ Checking every {CHECK_INTERVAL_MINUTES} minutes\n"
        f"🛂 Sponsorship filter: {'ON ✅' if REQUIRE_SPONSORSHIP_SIGNAL else 'OFF'}\n\n"
        "I'll ping you for jobs that:\n"
        "• Have an <b>external apply link</b> (not Easy Apply)\n"
        "• Mention <b>visa sponsorship / relocation</b> in the description\n"
        "• Match your ML / Computer Vision profile"
    )
    send_telegram(msg)


# ── LinkedIn scraper ───────────────────────────────────────────────────────────

def make_driver() -> webdriver.Chrome:
    import chromedriver_autoinstaller
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)


def linkedin_login(driver: webdriver.Chrome):
    log.info("Logging into LinkedIn...")
    driver.get("https://www.linkedin.com/login")
    wait = WebDriverWait(driver, 15)

    wait.until(EC.presence_of_element_located((By.ID, "username"))).send_keys(LINKEDIN_EMAIL)
    driver.find_element(By.ID, "password").send_keys(LINKEDIN_PASSWORD)
    driver.find_element(By.CSS_SELECTOR, "[type=submit]").click()

    time.sleep(4)
    if "checkpoint" in driver.current_url or "challenge" in driver.current_url:
        log.warning("LinkedIn is asking for verification. Solve it manually if running in non-headless mode.")

    wait.until(EC.url_contains("feed"))
    log.info("Logged in successfully.")
    time.sleep(2)


def search_jobs(driver, keywords: str, location: str) -> list:
    encoded_kw  = requests.utils.quote(keywords)
    encoded_loc = requests.utils.quote(location)
    # f_AL=false → show ALL jobs (not just Easy Apply)
    # sortBy=DD  → most recent first
    url = (f"https://www.linkedin.com/jobs/search/"
           f"?keywords={encoded_kw}&location={encoded_loc}"
           f"&f_AL=false&sortBy=DD&f_WT=2,1")  # f_WT=2,1 → remote + on-site

    log.info(f"Searching: '{keywords}' in '{location}'")
    driver.get(url)
    time.sleep(3)

    for _ in range(3):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    cards = soup.select("li.jobs-search-results__list-item")[:MAX_JOBS_PER_SEARCH]

    jobs = []
    for card in cards:
        try:
            title_el   = card.select_one("a.job-card-list__title, a.job-card-container__link")
            company_el = card.select_one(".job-card-container__primary-description, "
                                         ".artdeco-entity-lockup__subtitle")
            loc_el     = card.select_one(".job-card-container__metadata-item")
            posted_el  = card.select_one("time")

            if not title_el:
                continue

            title   = title_el.get_text(strip=True)
            company = company_el.get_text(strip=True) if company_el else "Unknown"

            # Filter by title relevance
            if not title_is_relevant(title):
                continue

            # Filter blocked companies
            if any(b.lower() in company.lower() for b in BLOCKED_COMPANIES):
                continue

            href = title_el.get("href", "")
            if not href.startswith("http"):
                href = "https://www.linkedin.com" + href

            jobs.append({
                "title":        title,
                "company":      company,
                "location":     loc_el.get_text(strip=True) if loc_el else location,
                "posted":       posted_el.get("datetime", "")[:10] if posted_el else "",
                "linkedin_url": href.split("?")[0],
                "search_kw":   keywords,
            })
        except Exception as e:
            log.debug(f"Card parse error: {e}")

    log.info(f"  → {len(jobs)} relevant job cards after filtering.")
    return jobs


def get_external_apply_url(driver, job: dict):
    """Return external apply URL if present, None if Easy Apply or no sponsorship signal."""
    try:
        driver.get(job["linkedin_url"])
        time.sleep(2)

        # Easy Apply = LinkedIn-hosted modal — skip these
        easy_apply = driver.find_elements(By.CSS_SELECTOR,
            "button.jobs-apply-button--top-card, "
            ".jobs-apply-button[data-job-id]")
        if easy_apply:
            btn_text = easy_apply[0].text.strip().lower()
            if "easy apply" in btn_text:
                return None

        # Check for sponsorship signal in job description
        if REQUIRE_SPONSORSHIP_SIGNAL:
            page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
            if not any(sig in page_text for sig in SPONSORSHIP_SIGNALS):
                log.debug(f"  No sponsorship signal found: {job['title']}")
                return None

        # External apply = an <a> tag linking away from LinkedIn
        ext_buttons = driver.find_elements(By.CSS_SELECTOR,
            "a.jobs-apply-button, "
            "a[data-tracking-control-name='public_jobs_apply-link-offsite_sign-in-modal'],"
            "a[data-tracking-control-name='public_jobs_apply-link-offsite'],"
            "a.apply-button")

        for btn in ext_buttons:
            href = btn.get_attribute("href") or ""
            if href and "linkedin.com" not in href and href.startswith("http"):
                return href

        # Fallback: scan page source
        soup = BeautifulSoup(driver.page_source, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if ("apply" in href.lower() and
                    "linkedin.com" not in href and
                    href.startswith("http")):
                return href

    except Exception as e:
        log.debug(f"Error checking {job['linkedin_url']}: {e}")

    return None


# ── Main job ───────────────────────────────────────────────────────────────────

def run_check():
    log.info(f"=== Check started at {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")
    seen = load_seen()
    new_count = 0

    driver = make_driver()
    try:
        linkedin_login(driver)

        for search in JOB_SEARCHES:
            try:
                jobs = search_jobs(driver, search["keywords"], search["location"])
            except Exception as e:
                log.error(f"Search failed for '{search['keywords']}': {e}")
                continue

            for job in jobs:
                jid = job_id(job["linkedin_url"])
                if jid in seen:
                    continue

                seen.add(jid)
                apply_url = get_external_apply_url(driver, job)

                if apply_url:
                    job["apply_url"] = apply_url
                    log.info(f"✅ External apply: {job['title']} @ {job['company']}")
                    send_telegram(format_job_message(job))
                    new_count += 1
                    time.sleep(1)
                else:
                    log.debug(f"  Easy Apply only: {job['title']} @ {job['company']}")

                time.sleep(1.5)

            time.sleep(2)  # pause between searches

    except Exception as e:
        log.error(f"Run failed: {e}")
    finally:
        driver.quit()
        save_seen(seen)

    summary = f"✅ Check done — {new_count} new external job(s) sent to Telegram." if new_count > 0 \
              else "ℹ️ Check done — no new external apply jobs found."
    log.info(summary)


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "YOUR_BOT_TOKEN" in TELEGRAM_BOT_TOKEN or "YOUR_CHAT_ID" in TELEGRAM_CHAT_ID:
        print("❌  Please fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in the config.")
        exit(1)
    if "YOUR_LINKEDIN_PASSWORD" in LINKEDIN_PASSWORD:
        print("❌  Please fill in your LINKEDIN_PASSWORD in the config.")
        exit(1)

    print("=" * 55)
    print("  LinkedIn → Telegram Notifier")
    print("  Sri Charan Sripadi | ML / Computer Vision")
    print(f"  {len(JOB_SEARCHES)} searches | every {CHECK_INTERVAL_MINUTES} min")
    print("=" * 55)

    send_startup_message()
    run_check()

    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(run_check)
    while True:
        schedule.run_pending()
        time.sleep(30)
