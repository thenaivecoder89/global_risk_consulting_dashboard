import os
import re
import json
import math
import requests
import xml.etree.ElementTree as et
from uuid import uuid4
from html import unescape
from urllib.parse import quote_plus, urlparse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# initializing environment variables
load_dotenv()
db_url = os.getenv("DB_URL")

# firing up db engine
engine = create_engine(
    url=db_url,
    pool_pre_ping=(1 == 1)
)

# parse source content
class data_parser:
    # initialize parser session
    def __init__(self):
        self.session = requests.session()
        self.headers = {"user-agent": "risk-momentum-etl/1.0"}

    # fetch text content
    def fetch_text(self, url):
        try:
            response = self.session.get(url, headers=self.headers, timeout=20)
            response.raise_for_status()
            return response.text
        except:
            return ""

    # fetch byte content
    def fetch_bytes(self, url):
        try:
            response = self.session.get(url, headers=self.headers, timeout=25)
            response.raise_for_status()
            return response.content
        except:
            return b""

    # parse html text
    def parse_html(self, html_text):
        clean = re.sub(r"(?is)<script.*?>.*?</script>", " ", html_text)
        clean = re.sub(r"(?is)<style.*?>.*?</style>", " ", clean)
        clean = re.sub(r"(?is)<[^>]+>", " ", clean)
        clean = unescape(clean)
        return re.sub(r"\s+", " ", clean).strip()

    # parse pdf bytes
    def parse_pdf(self, pdf_bytes):
        try:
            import fitz
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            pages = [page.get_text("text") for page in doc]
            return re.sub(r"\s+", " ", " ".join(pages)).strip()
        except:
            return ""

    # extract url domain
    def domain_from_url(self, url):
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    # check allowed domain
    def domain_allowed(self, url, allowed_domains):
        domain = self.domain_from_url(url)
        for allowed_domain in allowed_domains:
            if domain == allowed_domain or domain.endswith("." + allowed_domain):
                return 1
        return 0

    # parse rss date
    def parse_date(self, raw_date):
        try:
            return parsedate_to_datetime(raw_date).date()
        except:
            try:
                return datetime.fromisoformat(raw_date[:10]).date()
            except:
                return datetime.now(timezone.utc).date()

    # pull google news
    def google_news_items(self, query, allowed_domains, start_date, end_date, item_limit):
        url = "https://news.google.com/rss/search?q=" + quote_plus(query) + "&hl=en-us&gl=us&ceid=us:en"
        rss_text = self.fetch_text(url)
        items = []
        try:
            root = et.fromstring(rss_text)
        except:
            return items
        for item in root.findall(".//item")[:item_limit]:
            children = {child.tag.lower().split("}")[-1]: child for child in list(item)}
            try:
                title = children.get("title").text or ""
            except:
                title = ""
            try:
                link = children.get("link").text or ""
            except:
                link = ""
            try:
                desc = children.get("description").text or ""
            except:
                desc = ""
            try:
                raw_date = children.get("pubdate").text or ""
            except:
                raw_date = ""
            try:
                source_url = children.get("source").attrib.get("url", "")
                source_name = children.get("source").text or ""
            except:
                source_url = ""
                source_name = ""
            published_date = self.parse_date(raw_date)
            allowed = self.domain_allowed(source_url, allowed_domains) or self.domain_allowed(link, allowed_domains)
            if allowed and start_date <= published_date <= end_date:
                items.append({
                    "title": self.parse_html(title),
                    "description": self.parse_html(desc),
                    "url": link,
                    "source_url": source_url,
                    "source_name": source_name,
                    "published_date": published_date.isoformat()
                })
        return items

# compute and load data
class risk_practice_momentum_loader:
    # initialize loader settings
    def __init__(self, db_engine):
        self.engine = db_engine
        self.parser = data_parser()
        self.table_name = "risk_practice_momentum_index"
        self.topic_keywords = [
            "risk consulting",
            "risk advisory",
            "risk services",
            "enterprise risk",
            "risk management",
            "operational risk",
            "operational resilience",
            "technology risk",
            "cyber risk",
            "regulatory risk",
            "regulatory compliance",
            "financial crime",
            "forensic",
            "fraud investigation",
            "internal audit",
            "controls",
            "governance risk compliance",
            "third party risk",
            "model risk",
            "ai risk",
            "responsible ai"
        ]
        self.methodology_version = "risk_momentum_v1"
        self.news_domains = ["wsj.com", "ft.com", "bloomberg.com", "reuters.com", "apnews.com", "economist.com"]
        self.firms = {
            "ey": {
                "aliases": ["ey", "ernst young", "ernst & young"],
                "domains": ["ey.com"]
            },
            "kpmg": {
                "aliases": ["kpmg", "kpmg international"],
                "domains": ["kpmg.com"]
            },
            "deloitte": {
                "aliases": ["deloitte", "deloitte risk advisory"],
                "domains": ["deloitte.com"]
            },
            "pwc": {
                "aliases": ["pwc", "pricewaterhousecoopers", "pricewaterhouse coopers"],
                "domains": ["pwc.com"]
            },
            "mckinsey": {
                "aliases": ["mckinsey", "mckinsey company", "mckinsey & company"],
                "domains": ["mckinsey.com"]
            },
            "bain": {
                "aliases": ["bain company", "bain & company"],
                "domains": ["bain.com"]
            },
            "boston consulting": {
                "aliases": ["bcg", "boston consulting group"],
                "domains": ["bcg.com"]
            },
            "accenture": {
                "aliases": ["accenture"],
                "domains": ["accenture.com"]
            },
            "alvarez and marsal": {
                "aliases": ["alvarez and marsal", "alvarez & marsal"],
                "domains": ["alvarezandmarsal.com"]
            }
        }
        self.theme_words = {
            "cyber risk": [
                "cyber risk",
                "cybersecurity",
                "cyber security",
                "cyber resilience",
                "security operations",
                "incident response"
            ],
            "ai risk": [
                "ai risk",
                "responsible ai",
                "ai governance",
                "model risk",
                "algorithmic risk",
                "genai risk",
                "generative ai risk"
            ],
            "regulatory": [
                "regulatory",
                "regulation",
                "compliance",
                "supervisory",
                "conduct risk",
                "prudential"
            ],
            "forensic": [
                "forensic",
                "fraud",
                "investigation",
                "financial crime",
                "anti money laundering",
                "aml",
                "sanctions"
            ],
            "internal audit": [
                "internal audit",
                "controls",
                "sox",
                "control testing",
                "assurance"
            ],
            "enterprise risk": [
                "enterprise risk",
                "erm",
                "risk management",
                "risk transformation",
                "risk operating model"
            ],
            "third party risk": [
                "third party risk",
                "vendor risk",
                "supplier risk",
                "supply chain risk"
            ],
            "esg risk": [
                "climate risk",
                "sustainability risk",
                "esg risk",
                "nature risk"
            ],
            "operational resilience": [
                "operational resilience",
                "business resilience",
                "crisis management",
                "business continuity"
            ]
        }
        self.region_words = {
            "global": ["global", "worldwide", "international"],
            "middle east": ["middle east", "gcc", "uae", "united arab emirates", "saudi arabia", "qatar", "kuwait", "oman", "bahrain"],
            "india": ["india", "indian"],
            "europe": ["europe", "european union", "eu", "united kingdom", "uk"],
            "north america": ["united states", "u.s.", "usa", "canada", "north america"],
            "asia pacific": ["asia pacific", "apac", "singapore", "australia", "japan", "hong kong"],
            "africa": ["africa", "south africa"],
            "latin america": ["latin america", "brazil", "mexico"]
        }
        self.momentum_words = {
            "deal": [
                "acquisition",
                "acquired",
                "buys",
                "bought",
                "merger",
                "investment"
            ],
            "alliance": [
                "strategic alliance",
                "partnership",
                "collaboration",
                "collaborates with",
                "teams with",
                "joins forces"
            ],
            "platform_launch": [
                "launches",
                "launched",
                "platform",
                "solution",
                "tool",
                "hub",
                "center",
                "centre",
                "accelerator"
            ],
            "thought_leadership": [
                "report",
                "survey",
                "outlook",
                "study",
                "white paper",
                "insight",
                "perspective",
                "index"
            ],
            "hiring": [
                "job",
                "jobs",
                "career",
                "careers",
                "hiring",
                "vacancy",
                "open role",
                "job opening",
                "apply now"
            ],
            "official_activity": [
                "announces",
                "announced",
                "expands",
                "expanded",
                "launches",
                "launched",
                "appoints",
                "appointed",
                "opens",
                "opened"
            ]
        }
        self.exclude_url_words = [
            "/about",
            "/contact",
            "/people",
            "/profile",
            "/profiles",
            "/leadership",
            "/partners",
            "/offices",
            "/locations",
            "/home",
            "/careers/search",
            "/job-search",
            "/search-results"
        ]

        self.exclude_text_words = [
            "home page",
            "contact us",
            "office locations",
            "privacy policy",
            "terms of use",
            "cookie policy",
            "all jobs",
            "search jobs",
            "job search",
            "people profile",
            "partner profile"
        ]

    # score signal relevance
    def relevance_score(self, text_blob, source_url, official_domains):
        score = 0
        source_type = self.source_bucket(source_url, official_domains)

        risk_hit = self.has_phrase(text_blob, self.topic_keywords)
        momentum_hit = any(self.has_phrase(text_blob, words) for words in self.momentum_words.values())
        theme_hit = len(self.matched_labels(text_blob, self.theme_words)) > 0

        if risk_hit:
            score = score + 40

        if theme_hit:
            score = score + 20

        if momentum_hit:
            score = score + 20

        if source_type in ["official", "news"]:
            score = score + 10

        if self.has_phrase(text_blob, ["risk advisory", "risk consulting", "risk services", "enterprise risk", "cyber risk", "regulatory compliance"]):
            score = score + 10

        return min(100, score)

    # exclude weak pages
    def is_excluded(self, text_blob, source_url):
        clean_url = source_url.lower()
        clean_text = text_blob.lower()

        if any(word in clean_url for word in self.exclude_url_words):
            return 1

        if any(word in clean_text for word in self.exclude_text_words):
            return 1

        if len(clean_text) < 80:
            return 1

        return 0
    
    # classify signal type
    def signal_type(self, text_blob, source_url, official_domains):
        source_type = self.source_bucket(source_url, official_domains)

        if self.is_excluded(text_blob, source_url):
            return ""

        if not self.has_phrase(text_blob, self.topic_keywords):
            return ""

        if self.has_phrase(text_blob, self.momentum_words["deal"]):
            return "deal"

        if self.has_phrase(text_blob, self.momentum_words["alliance"]):
            return "alliance"

        if self.has_phrase(text_blob, self.momentum_words["platform_launch"]):
            return "platform_launch"

        if source_type == "official" and self.has_phrase(text_blob, self.momentum_words["hiring"]):
            return "hiring"

        if self.has_phrase(text_blob, self.momentum_words["thought_leadership"]):
            return "thought_leadership"

        if source_type == "official" and self.has_phrase(text_blob, self.momentum_words["official_activity"]):
            return "official_post"

        if source_type == "news":
            return "news"

        return ""

    # match clean phrase
    def has_phrase(self, text_blob, words):
        for word in words:
            pattern = r"(?<![a-z0-9])" + re.escape(word.lower()) + r"(?![a-z0-9])"
            if re.search(pattern, text_blob.lower()):
                return 1
        return 0
    
    # find matched labels
    def matched_labels(self, text_blob, label_map):
        labels = []
        for label, words in label_map.items():
            if self.has_phrase(text_blob, words):
                labels.append(label)
        return labels
    
    # classify source bucket
    def source_bucket(self, source_url, official_domains):
        if self.parser.domain_allowed(source_url, official_domains):
            return "official"
        if self.parser.domain_allowed(source_url, self.news_domains):
            return "news"
        return "other"

    # convert z-score to percentile-like 0-100 score
    def z_score_to_percentile_score(self, value, mean_value, std_value):
        if std_value == 0:
            return 50
        z_score = (value - mean_value) / std_value
        return round((0.5 * (1 + math.erf(z_score / math.sqrt(2)))) * 100, 2)

    # collect firm evidence
    def collect_firm_items(self, firm_name, firm_data, start_date, end_date):
        items = []
        query_suffixes = [
            "announces launches expands",
            "report survey outlook insight",
            "acquisition partnership alliance",
            "cyber regulatory forensic compliance",
            "internal audit controls enterprise risk",
            "jobs careers hiring"
        ]
        for alias in firm_data["aliases"]:
            for topic_keyword in self.topic_keywords:
                for query_suffix in query_suffixes:
                    base_query = "\"" + alias + "\" \"" + topic_keyword + "\" " + query_suffix + " after:" + start_date.isoformat() + " before:" + (end_date + timedelta(days=1)).isoformat()
                    items.extend(self.parser.google_news_items(base_query, self.news_domains, start_date, end_date, 8))
                    for domain in firm_data["domains"]:
                        official_query = base_query + " site:" + domain
                        items.extend(self.parser.google_news_items(official_query, [domain], start_date, end_date, 8))
        seen = set()
        clean_items = []
        for item in items:
            key = (item.get("title", "").lower(), item.get("source_url", ""))
            if key in seen:
                continue
            seen.add(key)
            text_blob = (item.get("title", "") + " " + item.get("description", "")).lower()
            source_url = item.get("source_url", "") or item.get("url", "")

            relevance_score = self.relevance_score(text_blob, source_url, firm_data["domains"])
            signal = self.signal_type(text_blob, source_url, firm_data["domains"])

            if relevance_score < 70:
                continue

            if not signal:
                continue

            item["firm_name"] = firm_name
            item["signal_type"] = signal
            item["signal_relevance_score"] = relevance_score
            item["source_bucket"] = self.source_bucket(source_url, firm_data["domains"])
            item["matched_themes"] = self.matched_labels(text_blob, self.theme_words)
            item["matched_regions"] = self.matched_labels(text_blob, self.region_words)
            clean_items.append(item)
        return clean_items

    # score firm momentum
    def score_firm(self, firm_name, items, start_date, end_date, ingestion_run_id):
        counts = {"news": 0, "hiring": 0, "deal": 0, "alliance": 0, "platform_launch": 0, "official_post": 0, "thought_leadership": 0}
        themes = []
        regions = []
        source_urls = []
        for item in items:
            signal = item.get("signal_type", "news")
            if signal in counts:
                counts[signal] = counts[signal] + 1
            themes.extend(item.get("matched_themes", []))
            regions.extend(item.get("matched_regions", []))
            source_urls.append(item.get("url", ""))
        theme_counts = {theme: themes.count(theme) for theme in sorted(set(themes))}
        region_counts = {region: regions.count(region) for region in sorted(set(regions))}
        dominant_themes = sorted(theme_counts, key=theme_counts.get, reverse=1)[:5]
        dominant_regions = sorted(region_counts, key=region_counts.get, reverse=1)[:5]
        raw_score_metrics = {
            "news_score": counts["news"] + counts["official_post"],
            "hiring_score": counts["hiring"],
            "deal_alliance_score": counts["deal"] + counts["alliance"],
            "theme_activity_score": len(dominant_themes) + counts["platform_launch"] + counts["thought_leadership"],
            "regional_activity_score": len(dominant_regions) + sum(region_counts.values()),
            "thought_leadership_score": counts["thought_leadership"] + counts["official_post"]
        }
        evidence_items = items[:20]
        source_quality_score = 100 if items else 0
        data_completeness_score = round(sum(1 for score in raw_score_metrics.values() if score > 0) / len(raw_score_metrics) * 100, 2)
        confidence_score = round(source_quality_score * 0.40 + data_completeness_score * 0.35 + min(100, len(items) * 8) * 0.25, 2)
        confidence_ratio = round(confidence_score / 100, 3)
        source_quality_ratio = round(source_quality_score / 100, 3)
        data_completeness_ratio = round(data_completeness_score / 100, 3)
        llm_context = {"method": "directional public signal scoring", "period": start_date.isoformat() + " to " + end_date.isoformat(), "top_titles": [item.get("title", "") for item in evidence_items[:8]], "score_note": "score is not revenue, market share, or confirmed commercial performance"}
        return {
            "analysis_period_start": start_date,
            "analysis_period_end": end_date,
            "firm_name": firm_name,
            "momentum_score": 0,
            "rank_in_period": 0,
            "news_score": 0,
            "hiring_score": 0,
            "deal_alliance_score": 0,
            "theme_activity_score": 0,
            "regional_activity_score": 0,
            "thought_leadership_score": 0,
            "news_signal_count": counts["news"],
            "hiring_signal_count": counts["hiring"],
            "deal_signal_count": counts["deal"],
            "alliance_signal_count": counts["alliance"],
            "platform_launch_signal_count": counts["platform_launch"],
            "official_post_signal_count": counts["official_post"],
            "thought_leadership_count": counts["thought_leadership"],
            "dominant_themes": dominant_themes,
            "dominant_regions": dominant_regions,
            "main_drivers": "",
            "driver_breakdown": "{}",
            "raw_signal_counts": json.dumps(counts, ensure_ascii=0),
            "feature_vector": json.dumps({"themes": theme_counts, "regions": region_counts, "signals": counts, "raw_score_metrics": raw_score_metrics, "scoring_method": "z_score_normalization"}, ensure_ascii=0),
            "llm_context": json.dumps(llm_context, ensure_ascii=0),
            "llm_summary": "",
            "evidence_items": json.dumps(evidence_items, ensure_ascii=0, default=str),
            "source_urls": json.dumps([url for url in source_urls if url][:30], ensure_ascii=0),
            "confidence_score": confidence_ratio,
            "source_quality_score": source_quality_ratio,
            "data_completeness_score": data_completeness_ratio,
            "methodology_version": self.methodology_version,
            "ingestion_run_id": ingestion_run_id,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "_raw_score_metrics": raw_score_metrics
        }

    # normalize raw component metrics across firms
    def apply_z_score_scoring(self, records):
        score_columns = ["news_score", "hiring_score", "deal_alliance_score", "theme_activity_score", "regional_activity_score", "thought_leadership_score"]
        for score_column in score_columns:
            values = [record["_raw_score_metrics"][score_column] for record in records]
            mean_value = sum(values) / len(values)
            std_value = math.sqrt(sum((value - mean_value) ** 2 for value in values) / len(values))
            if max(values) == 0:
                scores = [0 for value in values]
            else:
                scores = [self.z_score_to_percentile_score(value, mean_value, std_value) for value in values]
            for record, score in zip(records, scores):
                record[score_column] = score
        for record in records:
            driver_breakdown = {score_column: record[score_column] for score_column in score_columns}
            main_drivers = sorted(driver_breakdown, key=driver_breakdown.get, reverse=1)[:3]
            record["momentum_score"] = round(sum(driver_breakdown.values()) / len(driver_breakdown), 2)
            record["main_drivers"] = ", ".join(main_drivers).replace("_", " ")
            record["driver_breakdown"] = json.dumps(driver_breakdown, ensure_ascii=0)
            record["llm_summary"] = record["firm_name"] + " shows a momentum score of " + str(record["momentum_score"]) + " based on z-score normalized public evidence. main drivers are " + record["main_drivers"] + "."
            del record["_raw_score_metrics"]
        return records

    # push records database
    def push_records(self, records):
        columns = ["analysis_period_start", "analysis_period_end", "firm_name", "momentum_score", "rank_in_period", "news_score", "hiring_score", "deal_alliance_score", "theme_activity_score", "regional_activity_score", "thought_leadership_score", "news_signal_count", "hiring_signal_count", "deal_signal_count", "alliance_signal_count", "platform_launch_signal_count", "official_post_signal_count", "thought_leadership_count", "dominant_themes", "dominant_regions", "main_drivers", "driver_breakdown", "raw_signal_counts", "feature_vector", "llm_context", "llm_summary", "evidence_items", "source_urls", "confidence_score", "source_quality_score", "data_completeness_score", "methodology_version", "ingestion_run_id", "created_at", "updated_at"]
        column_text = ", ".join(columns)
        value_text = ", ".join([":" + column for column in columns])
        insert_sql = text("insert into " + self.table_name + " (" + column_text + ") values (" + value_text + ")")
        delete_sql = text("delete from " + self.table_name + " where analysis_period_start = :analysis_period_start and analysis_period_end = :analysis_period_end and methodology_version = :methodology_version")
        with self.engine.begin() as connection:
            if records:
                connection.execute(delete_sql, {"analysis_period_start": records[0]["analysis_period_start"], "analysis_period_end": records[0]["analysis_period_end"], "methodology_version": self.methodology_version})
                connection.execute(insert_sql, records)
        return records

    # run full load
    def run(self):
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=90)
        ingestion_run_id = "risk_momentum_" + str(uuid4())
        records = []
        for firm_name, firm_data in self.firms.items():
            items = self.collect_firm_items(firm_name, firm_data, start_date, end_date)
            records.append(self.score_firm(firm_name, items, start_date, end_date, ingestion_run_id))
        records = self.apply_z_score_scoring(records)
        records = sorted(records, key=lambda row: row["momentum_score"], reverse=1)
        for index, record in enumerate(records, start=1):
            record["rank_in_period"] = index
        return self.push_records(records)

# run full etl
def data_push_risk_practice_momentum_index():
    loader = risk_practice_momentum_loader(engine)
    return loader.run()

import time
if __name__ == "__main__":
   start_time = time.time()
   records = data_push_risk_practice_momentum_index()
   end_time = time.time()
   total_program_time = end_time - start_time
   print(f"Data scraping for risk practice momentum index complete with {len(records)} records populated in the table. Overall program execution time: {total_program_time/60:.2f} minutes.")
