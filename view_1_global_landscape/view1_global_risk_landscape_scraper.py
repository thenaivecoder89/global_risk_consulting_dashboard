"""
View 1 Scraper: Global Risk Consulting Practice Landscape

Purpose:
- Pull official, public, firm-level data needed for a management dashboard view.
- Extract firm scale indicators, risk-practice positioning, capability tags, source evidence,
  and confidence/missing-data notes.

Design:
- One simple file.
- No complex OOP structure.
- Uses a curated official-source registry.
- Does not estimate Risk Consulting revenue unless explicitly disclosed in a source.

Install:
    pip install httpx beautifulsoup4 lxml pymupdf pandas python-dateutil

Run:
    python view1_global_risk_landscape_scraper.py --out outputs/view1 --delay 1.5

Outputs:
    1. view1_global_landscape.csv
    2. view1_global_landscape.json
    3. source_extracts.csv
    4. source_extracts.json
    5. raw_text/*.txt

Notes:
- Some firm pages are JavaScript-heavy. This bare-bones scraper records extraction failures
  rather than using browser automation.
- Keep request rates low and respect each website's terms/robots policy.
"""

import argparse
import csv
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
import pandas as pd
from bs4 import BeautifulSoup

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

# ---------------------------------------------------------------------
# 1) Curated official source registry for View 1
# ---------------------------------------------------------------------

SOURCE_REGISTRY = [
    # Deloitte
    {
        "firm": "Deloitte",
        "firm_category": "Big 4",
        "source_type": "annual_revenue_release",
        "source_role": "scale",
        "url": "https://www.deloitte.com/global/en/about/press-room/global-revenue-announcement.html",
        "notes": "Official Deloitte FY revenue / people release. If this global URL redirects, try country mirror URLs manually."
    },
    {
        "firm": "Deloitte",
        "firm_category": "Big 4",
        "source_type": "official_service_page",
        "source_role": "practice_positioning",
        "url": "https://www.deloitte.com/global/en/services/consulting/services/risk-regulatory-forensic.html",
        "notes": "Official Deloitte Risk, Regulatory & Forensic service page."
    },

    # PwC
    {
        "firm": "PwC",
        "firm_category": "Big 4",
        "source_type": "annual_review",
        "source_role": "scale",
        "url": "https://www.pwc.com/gx/en/about/global-annual-review.html",
        "notes": "Official PwC Global Annual Review landing page."
    },
    {
        "firm": "PwC",
        "firm_category": "Big 4",
        "source_type": "annual_review_pdf",
        "source_role": "scale",
        "url": "https://www.pwc.com/gx/en/global-annual-review/2025/pwc-global-annual-review-2025.pdf",
        "notes": "Official PwC Global Annual Review PDF."
    },
    {
        "firm": "PwC",
        "firm_category": "Big 4",
        "source_type": "official_service_page",
        "source_role": "practice_positioning",
        "url": "https://www.pwc.com/us/en/services/consulting/risk-regulatory/enterprise-risk-management-controls.html",
        "notes": "Official PwC Enterprise Risk and Controls service page."
    },

    # EY
    {
        "firm": "EY",
        "firm_category": "Big 4",
        "source_type": "annual_report",
        "source_role": "scale",
        "url": "https://www.ey.com/en_gl/value-realized-annual-report",
        "notes": "Official EY Value Realized annual report landing page."
    },
    {
        "firm": "EY",
        "firm_category": "Big 4",
        "source_type": "annual_revenue_release",
        "source_role": "scale",
        "url": "https://www.ey.com/en_gl/newsroom/2025/10/ey-announces-global-revenue-of-us-53-2b-for-fiscal-year-2025",
        "notes": "Official EY FY2025 global revenue release."
    },
    {
        "firm": "EY",
        "firm_category": "Big 4",
        "source_type": "official_service_page",
        "source_role": "practice_positioning",
        "url": "https://www.ey.com/en_gl/services/consulting/risk",
        "notes": "Official EY risk consulting page; URL may redirect depending on EY site structure."
    },
    {
        "firm": "EY",
        "firm_category": "Big 4",
        "source_type": "official_service_page",
        "source_role": "practice_positioning",
        "url": "https://www.ey.com/en_gl/services/consulting/internal-audit",
        "notes": "Official EY Internal Audit page; useful as supporting risk-practice evidence."
    },

    # KPMG
    {
        "firm": "KPMG",
        "firm_category": "Big 4",
        "source_type": "annual_revenue_release",
        "source_role": "scale",
        "url": "https://kpmg.com/xx/en/media/press-releases/2025/12/kpmg-delivers-rise-in-global-revenue.html",
        "notes": "Official KPMG FY2025 global revenue release."
    },
    {
        "firm": "KPMG",
        "firm_category": "Big 4",
        "source_type": "corporate_reporting",
        "source_role": "scale",
        "url": "https://kpmg.com/xx/en/about/corporate-reporting.html",
        "notes": "Official KPMG corporate reporting page."
    },
    {
        "firm": "KPMG",
        "firm_category": "Big 4",
        "source_type": "official_service_page",
        "source_role": "practice_positioning",
        "url": "https://kpmg.com/xx/en/what-we-do/services/advisory/risk-consulting.html",
        "notes": "Official KPMG Risk Consulting page."
    },
    {
        "firm": "KPMG",
        "firm_category": "Big 4",
        "source_type": "official_solution_page",
        "source_role": "practice_positioning",
        "url": "https://kpmg.com/xx/en/what-we-do/services/advisory/risk-consulting/kpmg-risk-hub.html",
        "notes": "Official KPMG Risk Hub page; useful for GRC/platform-led risk positioning."
    },

    # Accenture
    {
        "firm": "Accenture",
        "firm_category": "Tech / Transformation Consulting",
        "source_type": "annual_report",
        "source_role": "scale",
        "url": "https://www.accenture.com/us-en/about/company/annual-report",
        "notes": "Official Accenture annual reports page."
    },
    {
        "firm": "Accenture",
        "firm_category": "Tech / Transformation Consulting",
        "source_type": "annual_report_pdf",
        "source_role": "scale",
        "url": "https://www.accenture.com/content/dam/accenture/final/accenture-com/document-4/Annual-Report-2025.pdf",
        "notes": "Official Accenture 2025 annual report PDF."
    },
    {
        "firm": "Accenture",
        "firm_category": "Tech / Transformation Consulting",
        "source_type": "corporate_fact_sheet",
        "source_role": "scale",
        "url": "https://newsroom.accenture.com/fact-sheet",
        "notes": "Official Accenture fact sheet."
    },
    {
        "firm": "Accenture",
        "firm_category": "Tech / Transformation Consulting",
        "source_type": "official_service_page",
        "source_role": "practice_positioning",
        "url": "https://www.accenture.com/us-en/services/cybersecurity",
        "notes": "Official Accenture Cybersecurity services page; proxy for risk-related technology consulting."
    },

    # McKinsey
    {
        "firm": "McKinsey",
        "firm_category": "Strategy House",
        "source_type": "official_service_page",
        "source_role": "practice_positioning",
        "url": "https://www.mckinsey.com/capabilities/risk-and-resilience/how-we-help-clients",
        "notes": "Official McKinsey Risk & Resilience practice page."
    },

    # BCG
    {
        "firm": "BCG",
        "firm_category": "Strategy House",
        "source_type": "official_service_page",
        "source_role": "practice_positioning",
        "url": "https://www.bcg.com/capabilities/risk-management-and-compliance/overview",
        "notes": "Official BCG Risk Management and Compliance page."
    },

    # Bain
    {
        "firm": "Bain",
        "firm_category": "Strategy House",
        "source_type": "official_service_page",
        "source_role": "practice_positioning",
        "url": "https://www.bain.com/industry-expertise/financial-services/risk-finance-compliance/",
        "notes": "Official Bain Risk, Finance and Compliance page."
    },

    # A&M
    {
        "firm": "Alvarez & Marsal",
        "firm_category": "Restructuring / Performance Improvement Advisory",
        "source_type": "official_service_page",
        "source_role": "practice_positioning",
        "url": "https://www.alvarezandmarsal.com/expertise/regulatoryrisk-compliance",
        "notes": "Official A&M Regulatory & Risk Advisory page."
    },
]


# ---------------------------------------------------------------------
# 2) Taxonomy and extraction dictionaries
# ---------------------------------------------------------------------

RISK_SEGMENT_KEYWORDS = {
    "Operational Risk & Resilience": [
        "operational risk", "resilience", "business continuity", "crisis",
        "supply chain", "third-party risk", "third party risk", "outsourcing",
        "process risk", "enterprise risk management", "ERM"
    ],
    "Financial Risk": [
        "financial risk", "credit risk", "market risk", "liquidity risk",
        "treasury", "capital", "stress testing", "balance sheet",
        "model risk", "prudential risk"
    ],
    "Technology Risk / Cyber / Digital Trust": [
        "technology risk", "digital risk", "cyber", "cybersecurity",
        "cloud risk", "data governance", "privacy", "digital trust",
        "IT risk", "information security", "security operations"
    ],
    "Internal Audit, Controls & Assurance": [
        "internal audit", "controls", "control assurance", "internal controls",
        "SOX", "Sarbanes-Oxley", "ICFR", "ITGC", "audit analytics",
        "continuous auditing", "continuous monitoring", "risk assurance"
    ],
    "Regulatory & Compliance": [
        "regulatory", "regulation", "compliance", "conduct risk", "AML",
        "sanctions", "financial crime", "risk and compliance",
        "regulatory change", "regulatory remediation"
    ],
    "Forensic / Financial Crime / Investigations": [
        "forensic", "investigation", "investigations", "fraud", "dispute",
        "litigation", "anti-bribery", "corruption", "misconduct",
        "financial crime"
    ],
    "ESG / Climate / Sustainability Risk": [
        "ESG", "sustainability", "climate risk", "transition risk",
        "physical risk", "sustainable", "non-financial reporting"
    ],
    "AI Risk / Responsible AI / Model Governance": [
        "AI risk", "responsible AI", "artificial intelligence", "GenAI",
        "generative AI", "agentic AI", "model governance",
        "AI governance", "machine learning", "algorithm"
    ],
    "Managed Risk Services / Platforms": [
        "managed services", "managed risk", "platform", "GRC",
        "governance risk and compliance", "ServiceNow", "Archer",
        "OpenPages", "automation", "continuous controls"
    ],
}

SCALE_KEYWORDS = [
    "revenue", "global revenue", "annual revenue", "gross revenues",
    "employees", "people", "workforce", "professionals", "headcount",
    "countries", "territories", "offices", "advisory", "consulting"
]

PRACTICE_POSITIONING_KEYWORDS = [
    "risk", "risk consulting", "risk advisory", "risk and resilience",
    "risk management", "regulatory", "compliance", "cyber", "forensic",
    "internal audit", "controls", "assurance", "resilience"
]


# ---------------------------------------------------------------------
# 3) Utility functions
# ---------------------------------------------------------------------

def now_utc_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def safe_filename(value):
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return value[:150].strip("_") or "file"


def get_domain(url):
    return urlparse(url).netloc.lower()


def robots_allowed(url, user_agent="RiskIntelBot", timeout=10):
    """
    Basic robots.txt check with an explicit timeout.

    Why this exists:
    - Python's RobotFileParser.read() internally uses urllib and can hang on
      some domains because the scraper does not control its timeout cleanly.
    - This version fetches robots.txt through httpx with a bounded timeout,
      then parses the returned robots.txt text.

    Conservative behavior:
    - If robots.txt cannot be fetched within timeout, this function returns True.
    - The actual page fetch is still protected by fetch_url's timeout.
    """
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    headers = {
        "User-Agent": "RiskIntelBot/1.0 (+review-purpose; contact: your-email@example.com)",
        "Accept": "text/plain,*/*;q=0.8",
    }

    try:
        timeout_config = httpx.Timeout(
            timeout,
            connect=min(5, timeout),
            read=timeout,
            write=5,
            pool=5
        )

        response = httpx.get(
            robots_url,
            timeout=timeout_config,
            follow_redirects=True,
            headers=headers,
        )

        # If robots.txt is unavailable, do not freeze or fail the whole scraper.
        if response.status_code >= 400:
            return True

        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.parse(response.text.splitlines())

        return rp.can_fetch(user_agent, url)

    except Exception:
        # Do not let a slow/unavailable robots.txt endpoint freeze the scraper.
        return True


def fetch_url(url, timeout=60):
    """
    Fetch HTML/PDF content with explicit connect/read/write/pool timeouts.

    Notes:
    - The browser-like User-Agent helps with public pages that vary response
      behavior based on User-Agent.
    - This does not bypass authentication, paywalls, cookie walls, or access controls.
    - Cookie banners are usually JavaScript/browser-layer issues. Since this
      scraper uses httpx and BeautifulSoup, it does not click cookie banners.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36 "
            "RiskIntelBot/1.0 (+review-purpose; contact: your-email@example.com)"
        ),
        "Accept": "text/html,application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    timeout_config = httpx.Timeout(
        timeout,
        connect=15,
        read=timeout,
        write=15,
        pool=15
    )

    with httpx.Client(
        timeout=timeout_config,
        follow_redirects=True,
        headers=headers
    ) as client:
        response = client.get(url)
        response.raise_for_status()

    content_type = response.headers.get("content-type", "").lower()

    return {
        "final_url": str(response.url),
        "status_code": response.status_code,
        "content_type": content_type,
        "content_bytes": response.content,
        "content_text": response.text
        if "text" in content_type or "html" in content_type or "xml" in content_type
        else "",
    }


def extract_html_text(html):
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript", "svg", "form", "iframe"]):
        tag.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else ""

    meta_description = ""
    desc_tag = soup.find("meta", attrs={"name": "description"})
    if desc_tag and desc_tag.get("content"):
        meta_description = desc_tag.get("content", "").strip()

    headings = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])]
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all(["p", "li", "td", "th"])]

    # Also collect visible anchor text; service pages sometimes use cards/links for capabilities.
    anchors = [a.get_text(" ", strip=True) for a in soup.find_all("a")]

    chunks = []
    for value in [title, meta_description] + headings + paragraphs + anchors:
        if value and len(value.strip()) > 1:
            chunks.append(value.strip())

    text = "\n".join(chunks)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)

    return {
        "title": title,
        "meta_description": meta_description,
        "text": text,
    }


def extract_pdf_text(pdf_bytes):
    if fitz is None:
        raise RuntimeError("PyMuPDF is not installed. Install it with: pip install pymupdf")

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    title = ""

    metadata = doc.metadata or {}
    if metadata.get("title"):
        title = metadata["title"]

    for idx, page in enumerate(doc, start=1):
        page_text = page.get_text("text") or ""
        if page_text.strip():
            pages.append(f"\n\n--- PAGE {idx} ---\n{page_text}")

    text = "\n".join(pages)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)

    return {
        "title": title,
        "meta_description": "",
        "text": text,
    }


def split_sentences(text):
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return []

    # Simple sentence splitter. Good enough for extraction review.
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", cleaned)
    return [s.strip() for s in sentences if len(s.strip()) >= 40]


def first_relevant_sentences(text, keywords, max_sentences=3):
    sentences = split_sentences(text)
    selected = []

    for sentence in sentences:
        lower_sentence = sentence.lower()
        if any(k.lower() in lower_sentence for k in keywords):
            selected.append(sentence)
        if len(selected) >= max_sentences:
            break

    return " ".join(selected)


def find_keyword_contexts(text, keywords, window=220, max_hits=8):
    contexts = []
    lower_text = text.lower()

    for keyword in keywords:
        keyword_lower = keyword.lower()
        pos = lower_text.find(keyword_lower)
        if pos >= 0:
            start = max(0, pos - window)
            end = min(len(text), pos + len(keyword) + window)
            excerpt = text[start:end]
            excerpt = re.sub(r"\s+", " ", excerpt).strip()
            contexts.append({
                "keyword": keyword,
                "excerpt": excerpt
            })

        if len(contexts) >= max_hits:
            break

    return contexts


# ---------------------------------------------------------------------
# 4) Field extractors for View 1
# ---------------------------------------------------------------------

def extract_scale_metrics(text):
    """
    Extracts firm-scale indicators as text evidence.
    This deliberately avoids hard-coded firm-specific values and avoids
    over-interpreting ambiguous numbers.
    """
    clean = re.sub(r"\s+", " ", text or "")

    # Currency amount patterns: US$70.5 billion, $39.8 billion, USD 69.7B, US$24.3bn
    money_pattern = re.compile(
        r"(?i)\b(?:US\$|USD|\$)\s?\d{1,4}(?:,\d{3})*(?:\.\d+)?\s?(?:billion|bn|million|m)\b"
    )

    # Number + people/professional/workforce patterns.
    people_pattern = re.compile(
        r"(?i)\b(?:over|around|approximately|more than|nearly|about)?\s?"
        r"\d{1,3}(?:,\d{3})+(?:\+)?\s?"
        r"(?:people|employees|workforce|professionals|colleagues|staff)\b"
    )

    # Countries/territories/offices patterns.
    footprint_pattern = re.compile(
        r"(?i)\b\d{1,3}\s?(?:countries|territories|markets|offices)\b"
    )

    money_hits = money_pattern.findall(clean)
    people_hits = people_pattern.findall(clean)
    footprint_hits = footprint_pattern.findall(clean)

    # Pull specific context around important scale keywords.
    revenue_context = first_relevant_sentences(clean, ["revenue", "revenues", "financial performance"], max_sentences=3)
    people_context = first_relevant_sentences(clean, ["people", "employees", "workforce", "professionals", "headcount"], max_sentences=3)
    advisory_context = first_relevant_sentences(clean, ["advisory", "consulting", "risk", "strategy"], max_sentences=3)
    footprint_context = first_relevant_sentences(clean, ["countries", "territories", "markets", "offices"], max_sentences=2)

    return {
        "money_amounts_found": list(dict.fromkeys(money_hits))[:12],
        "people_amounts_found": list(dict.fromkeys(people_hits))[:12],
        "footprint_amounts_found": list(dict.fromkeys(footprint_hits))[:12],
        "revenue_evidence": revenue_context,
        "people_evidence": people_context,
        "advisory_consulting_evidence": advisory_context,
        "footprint_evidence": footprint_context,
    }


def classify_risk_segments(text):
    lower_text = (text or "").lower()
    segment_hits = {}
    all_capability_tags = []

    for segment, keywords in RISK_SEGMENT_KEYWORDS.items():
        hits = []
        for keyword in keywords:
            if keyword.lower() in lower_text:
                hits.append(keyword)

        if hits:
            segment_hits[segment] = list(dict.fromkeys(hits))
            all_capability_tags.extend(hits)

    # Simple coverage strength for View 1.
    segment_count = len(segment_hits)
    keyword_count = sum(len(v) for v in segment_hits.values())

    if keyword_count >= 15 or segment_count >= 5:
        coverage_strength = "High"
    elif keyword_count >= 6 or segment_count >= 3:
        coverage_strength = "Medium"
    elif keyword_count > 0:
        coverage_strength = "Low"
    else:
        coverage_strength = "Not evidenced"

    return {
        "risk_segments_evidenced": list(segment_hits.keys()),
        "risk_segment_keyword_hits": segment_hits,
        "risk_capability_tags": list(dict.fromkeys(all_capability_tags)),
        "risk_coverage_strength": coverage_strength,
    }


def extract_practice_positioning(text):
    positioning = first_relevant_sentences(text, PRACTICE_POSITIONING_KEYWORDS, max_sentences=4)
    contexts = find_keyword_contexts(text, PRACTICE_POSITIONING_KEYWORDS, max_hits=5)
    return {
        "risk_practice_positioning_statement": positioning,
        "practice_positioning_contexts": contexts,
    }


def source_confidence(source_type, status, text_length):
    if status != "success":
        return "Low"

    if text_length < 500:
        return "Medium"

    if source_type in {
        "annual_report", "annual_report_pdf", "annual_review", "annual_review_pdf",
        "annual_revenue_release", "corporate_reporting", "corporate_fact_sheet",
        "official_service_page", "official_solution_page"
    }:
        return "High"

    return "Medium"


def missing_notes_for_firm(row):
    notes = []

    if not row.get("money_amounts_found"):
        notes.append("No revenue/currency amount extracted from available sources.")

    if not row.get("people_amounts_found"):
        notes.append("No explicit workforce/headcount amount extracted from available sources.")

    if not row.get("risk_segments_evidenced"):
        notes.append("No risk segment keywords extracted from practice-positioning sources.")

    if not row.get("risk_practice_positioning_statement"):
        notes.append("No clear risk-practice positioning sentence extracted.")

    if not row.get("advisory_consulting_evidence"):
        notes.append("No advisory/consulting-specific evidence extracted; use firm-level scale only.")

    notes.append("Do not treat extracted firm-scale data as Risk Consulting-specific revenue or headcount unless explicitly stated in the source.")

    return " | ".join(notes)


# ---------------------------------------------------------------------
# 5) Main scraper
# ---------------------------------------------------------------------

def process_source(source, raw_text_dir, respect_robots=True):
    url = source["url"]
    captured_at = now_utc_iso()

    record = {
        **source,
        "captured_at": captured_at,
        "final_url": "",
        "http_status": "",
        "content_type": "",
        "title": "",
        "meta_description": "",
        "text_length": 0,
        "content_hash": "",
        "extract_status": "not_started",
        "error": "",
        "raw_text_path": "",
        "scale_metrics": {},
        "risk_classification": {},
        "practice_positioning": {},
        "source_confidence": "Low",
    }

    try:
        if respect_robots and not robots_allowed(url):
            record["extract_status"] = "blocked_by_robots"
            record["error"] = "robots.txt does not allow fetching this URL for the configured user agent."
            return record

        fetched = fetch_url(url)
        record["final_url"] = fetched["final_url"]
        record["http_status"] = fetched["status_code"]
        record["content_type"] = fetched["content_type"]

        is_pdf = "pdf" in fetched["content_type"] or url.lower().endswith(".pdf")
        if is_pdf:
            extracted = extract_pdf_text(fetched["content_bytes"])
        else:
            extracted = extract_html_text(fetched["content_text"])

        text = extracted["text"] or ""
        title = extracted["title"] or ""

        record["title"] = title
        record["meta_description"] = extracted.get("meta_description", "")
        record["text_length"] = len(text)
        record["content_hash"] = sha256_text(text)
        record["extract_status"] = "success"

        # Save raw text for audit/evidence review.
        raw_name = safe_filename(f"{source['firm']}_{source['source_type']}_{record['content_hash'][:10]}.txt")
        raw_path = raw_text_dir / raw_name
        raw_path.write_text(text, encoding="utf-8")
        record["raw_text_path"] = str(raw_path)

        record["scale_metrics"] = extract_scale_metrics(text)
        record["risk_classification"] = classify_risk_segments(text)
        record["practice_positioning"] = extract_practice_positioning(text)
        record["source_confidence"] = source_confidence(source["source_type"], "success", len(text))

    except Exception as exc:
        record["extract_status"] = "failed"
        record["error"] = str(exc)
        record["source_confidence"] = "Low"

    return record


def flatten_source_record(record):
    scale = record.get("scale_metrics") or {}
    risk = record.get("risk_classification") or {}
    positioning = record.get("practice_positioning") or {}

    return {
        "firm": record.get("firm"),
        "firm_category": record.get("firm_category"),
        "source_type": record.get("source_type"),
        "source_role": record.get("source_role"),
        "url": record.get("url"),
        "final_url": record.get("final_url"),
        "captured_at": record.get("captured_at"),
        "http_status": record.get("http_status"),
        "content_type": record.get("content_type"),
        "title": record.get("title"),
        "meta_description": record.get("meta_description"),
        "text_length": record.get("text_length"),
        "content_hash": record.get("content_hash"),
        "extract_status": record.get("extract_status"),
        "error": record.get("error"),
        "source_confidence": record.get("source_confidence"),
        "raw_text_path": record.get("raw_text_path"),
        "money_amounts_found": json.dumps(scale.get("money_amounts_found", []), ensure_ascii=False),
        "people_amounts_found": json.dumps(scale.get("people_amounts_found", []), ensure_ascii=False),
        "footprint_amounts_found": json.dumps(scale.get("footprint_amounts_found", []), ensure_ascii=False),
        "revenue_evidence": scale.get("revenue_evidence", ""),
        "people_evidence": scale.get("people_evidence", ""),
        "advisory_consulting_evidence": scale.get("advisory_consulting_evidence", ""),
        "footprint_evidence": scale.get("footprint_evidence", ""),
        "risk_coverage_strength": risk.get("risk_coverage_strength", ""),
        "risk_segments_evidenced": json.dumps(risk.get("risk_segments_evidenced", []), ensure_ascii=False),
        "risk_capability_tags": json.dumps(risk.get("risk_capability_tags", []), ensure_ascii=False),
        "risk_segment_keyword_hits": json.dumps(risk.get("risk_segment_keyword_hits", {}), ensure_ascii=False),
        "risk_practice_positioning_statement": positioning.get("risk_practice_positioning_statement", ""),
        "practice_positioning_contexts": json.dumps(positioning.get("practice_positioning_contexts", []), ensure_ascii=False),
        "notes": record.get("notes", ""),
    }


def combine_unique_json_lists(values):
    combined = []
    for value in values:
        if not value:
            continue

        try:
            parsed = json.loads(value) if isinstance(value, str) else value
        except Exception:
            parsed = []

        if isinstance(parsed, list):
            for item in parsed:
                if item and item not in combined:
                    combined.append(item)

    return combined


def first_non_empty(values):
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value:
            return value
    return ""


def build_view1_firm_rows(source_df):
    rows = []

    if source_df.empty:
        return pd.DataFrame()

    for firm, group in source_df.groupby("firm", dropna=False):
        firm_category = first_non_empty(group["firm_category"].tolist())

        scale_group = group[group["source_role"] == "scale"]
        practice_group = group[group["source_role"] == "practice_positioning"]

        # Pull all extracted numeric candidates rather than forcing one answer.
        money = combine_unique_json_lists(group["money_amounts_found"].tolist())
        people = combine_unique_json_lists(group["people_amounts_found"].tolist())
        footprint = combine_unique_json_lists(group["footprint_amounts_found"].tolist())
        segments = combine_unique_json_lists(practice_group["risk_segments_evidenced"].tolist())
        tags = combine_unique_json_lists(practice_group["risk_capability_tags"].tolist())

        successful_sources = group[group["extract_status"] == "success"]
        successful_urls = successful_sources["final_url"].replace("", pd.NA).dropna().unique().tolist()
        source_urls = group["url"].dropna().unique().tolist()

        # Use the first useful context statements.
        revenue_evidence = first_non_empty(scale_group["revenue_evidence"].tolist())
        people_evidence = first_non_empty(scale_group["people_evidence"].tolist())
        advisory_evidence = first_non_empty(scale_group["advisory_consulting_evidence"].tolist())
        footprint_evidence = first_non_empty(scale_group["footprint_evidence"].tolist())
        positioning = first_non_empty(practice_group["risk_practice_positioning_statement"].tolist())

        risk_strengths = [x for x in practice_group["risk_coverage_strength"].tolist() if x]
        if "High" in risk_strengths:
            risk_coverage_strength = "High"
        elif "Medium" in risk_strengths:
            risk_coverage_strength = "Medium"
        elif "Low" in risk_strengths:
            risk_coverage_strength = "Low"
        else:
            risk_coverage_strength = "Not evidenced"

        if len(successful_sources) == len(group) and len(group) > 0:
            extraction_quality = "High"
        elif len(successful_sources) > 0:
            extraction_quality = "Medium"
        else:
            extraction_quality = "Low"

        row = {
            "firm": firm,
            "firm_category": firm_category,
            "data_view": "View 1 - Global Risk Consulting Practice Landscape",
            "firm_scale_metric_candidates": json.dumps(money, ensure_ascii=False),
            "workforce_metric_candidates": json.dumps(people, ensure_ascii=False),
            "footprint_metric_candidates": json.dumps(footprint, ensure_ascii=False),
            "revenue_evidence": revenue_evidence,
            "people_evidence": people_evidence,
            "advisory_consulting_evidence": advisory_evidence,
            "footprint_evidence": footprint_evidence,
            "risk_practice_positioning_statement": positioning,
            "risk_segments_evidenced": json.dumps(segments, ensure_ascii=False),
            "risk_capability_tags": json.dumps(tags, ensure_ascii=False),
            "risk_coverage_strength": risk_coverage_strength,
            "source_urls": json.dumps(source_urls, ensure_ascii=False),
            "successful_source_urls": json.dumps(successful_urls, ensure_ascii=False),
            "source_count": int(len(group)),
            "successful_source_count": int(len(successful_sources)),
            "extraction_quality": extraction_quality,
            "captured_at_utc": now_utc_iso(),
        }

        row["missing_data_and_usage_notes"] = missing_notes_for_firm(row)
        rows.append(row)

    return pd.DataFrame(rows).sort_values(["firm_category", "firm"]).reset_index(drop=True)


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main(
        out="outputs/view1_data",
        limit=0,
        no_robots=False,
        delay=1.5
):
    start_time = time.time()
    start_time_value = datetime.fromtimestamp(start_time).date()
    print(f"Scraper start time: {datetime.strftime(start_time_value, "%d/%m/%Y, %H:%M:%S")}")
    # parser = argparse.ArgumentParser()
    # parser.add_argument("--out", default="outputs/view1", help="Output directory")
    # parser.add_argument("--delay", type=float, default=1.5, help="Delay between source requests in seconds")
    # parser.add_argument("--no-robots", action="store_true", help="Disable robots.txt check")
    # parser.add_argument("--limit", type=int, default=0, help="Limit number of sources for testing; 0 means all")
    # args = parser.parse_args()

    out_dir = Path(out)
    raw_text_dir = out_dir / "raw_text"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_text_dir.mkdir(parents=True, exist_ok=True)

    registry = SOURCE_REGISTRY[:limit] if limit and limit > 0 else SOURCE_REGISTRY

    print(f"Starting View 1 scrape for {len(registry)} official sources.")
    print(f"Output directory: {out_dir}")

    records = []

    for idx, source in enumerate(registry, start=1):
        print(
            f"[{idx}/{len(registry)}] {source['firm']} | {source['source_type']} | {source['url']}",
            flush=True
        )
        record = process_source(source, raw_text_dir, respect_robots=not no_robots)
        records.append(record)
        print(
            f"    status={record['extract_status']} "
            f"text_length={record['text_length']} "
            f"error={record['error'][:120] if record['error'] else ''}",
            flush=True
        )

        if idx < len(registry):
            time.sleep(max(0, delay))

    flat_records = [flatten_source_record(r) for r in records]
    source_df = pd.DataFrame(flat_records)
    view1_df = build_view1_firm_rows(source_df)
    view1_json = view1_df.to_json()
    view1_json_output = json.dumps(view1_json, indent=4)

    # source_csv = out_dir / "source_extracts.csv"
    # source_json = out_dir / "source_extracts.json"
    # view1_csv = out_dir / "view1_global_landscape.csv"
    # view1_json = out_dir / "view1_global_landscape.json"

    # source_df.to_csv(source_csv, index=False, quoting=csv.QUOTE_MINIMAL)
    # view1_df.to_csv(view1_csv, index=False, quoting=csv.QUOTE_MINIMAL)

    # save_json(source_json, flat_records)
    # save_json(view1_json, view1_df.to_dict(orient="records"))

    print("\nDone.")
    # print(f"Source extracts CSV: {source_csv}")
    # print(f"Source extracts JSON: {source_json}")
    # print(f"View 1 CSV: {view1_csv}")
    # print(f"View 1 JSON: {view1_json}")
    print("\nImportant: Review evidence columns manually before presenting to management.")

    end_time = time.time()
    end_time_value = datetime.fromtimestamp(end_time).date()
    print(f"Scraper end time: {datetime.strftime(end_time_value, "%d/%m/%Y, %H:%M:%S")}")
    program_runtime = end_time - start_time
    print(f"Overall program runtime: {program_runtime:.2f} seconds.")

    return view1_json_output


if __name__ == "__main__":
    print("Output of view 1 scraper program:\n")
    print(main())