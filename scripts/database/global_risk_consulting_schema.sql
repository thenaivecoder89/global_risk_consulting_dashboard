-- ============================================================
-- 1. RISK PRACTICE MOMENTUM INDEX
-- Grain: one row per firm per analysis period
-- Purpose: directional public-signal momentum score by firm
-- ===========================================================
create table if not exists risk_practice_momentum_index(
    id BIGSERIAL PRIMARY KEY,
    analysis_period_start DATE NOT NULL,
    analysis_period_end DATE NOT NULL,
    firm_name TEXT NOT NULL,
    momentum_score NUMERIC(5,2) CHECK (momentum_score BETWEEN 0 AND 100),
    rank_in_period INTEGER,
    -- Component scores
    news_score NUMERIC(5,2) CHECK (news_score BETWEEN 0 AND 100),
    hiring_score NUMERIC(5,2) CHECK (hiring_score BETWEEN 0 AND 100),
    deal_alliance_score NUMERIC(5,2) CHECK (deal_alliance_score BETWEEN 0 AND 100),
    theme_activity_score NUMERIC(5,2) CHECK (theme_activity_score BETWEEN 0 AND 100),
    regional_activity_score NUMERIC(5,2) CHECK (regional_activity_score BETWEEN 0 AND 100),
    thought_leadership_score NUMERIC(5,2) CHECK (thought_leadership_score BETWEEN 0 AND 100),
    -- Raw signal counts
    news_signal_count INTEGER DEFAULT 0,
    hiring_signal_count INTEGER DEFAULT 0,
    deal_signal_count INTEGER DEFAULT 0,
    alliance_signal_count INTEGER DEFAULT 0,
    platform_launch_signal_count INTEGER DEFAULT 0,
    official_post_signal_count INTEGER DEFAULT 0,
    thought_leadership_count INTEGER DEFAULT 0,
    dominant_themes TEXT[],
    dominant_regions TEXT[],
    main_drivers TEXT,
    -- ML-friendly structured fields
    driver_breakdown JSONB DEFAULT '{}'::JSONB,
    raw_signal_counts JSONB DEFAULT '{}'::JSONB,
    feature_vector JSONB DEFAULT '{}'::JSONB,
    -- LLM-friendly fields
    llm_context TEXT,
    llm_summary TEXT,
    evidence_items JSONB DEFAULT '[]'::JSONB,
    source_urls JSONB DEFAULT '[]'::JSONB,
    confidence_score NUMERIC(4,3) CHECK (confidence_score BETWEEN 0 AND 1),
    source_quality_score NUMERIC(4,3) CHECK (source_quality_score BETWEEN 0 AND 1),
    data_completeness_score NUMERIC(4,3) CHECK (data_completeness_score BETWEEN 0 AND 1),
    methodology_version TEXT DEFAULT 'mvp_v1',
    ingestion_run_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_momentum_firm_period UNIQUE (
        analysis_period_start,
        analysis_period_end,
        firm_name,
        methodology_version
    )
);
-- ============================================================
-- 2. HIRING INTENSITY INDEX
-- Grain: one row per firm-region-theme-seniority-period
-- Purpose: proxy for capability investment using official company career portals
-- ============================================================
create table if not exists hiring_intensity_index(
    id BIGSERIAL PRIMARY KEY,
    -- Period / reporting window
    analysis_period_start DATE NOT NULL,
    analysis_period_end DATE NOT NULL,
    -- Firm and geography
    firm_name TEXT NOT NULL,
    region TEXT,
    country TEXT,
    city TEXT,
    -- Hiring classification
    risk_capability_theme TEXT,
    seniority_level TEXT,
    job_type TEXT,
    -- Core hiring intensity metrics
    hiring_intensity_score NUMERIC(5,2) CHECK (hiring_intensity_score BETWEEN 0 AND 100),
    rank_in_segment INTEGER,
    active_job_posting_count INTEGER DEFAULT 0,
    new_job_posting_count INTEGER DEFAULT 0,
    closed_job_posting_count INTEGER DEFAULT 0,
    refreshed_job_posting_count INTEGER DEFAULT 0,
    -- Official career portal source fields
    official_company_portal_job_count INTEGER DEFAULT 0,
    official_company_portal_unique_requisition_count INTEGER DEFAULT 0,
    multi_location_posting_count INTEGER DEFAULT 0,
    duplicate_requisition_count INTEGER DEFAULT 0,
    deduplicated_job_posting_count INTEGER DEFAULT 0,
    career_portal_pages_scanned INTEGER DEFAULT 0,
    career_portal_pages_successful INTEGER DEFAULT 0,
    career_portal_pages_failed INTEGER DEFAULT 0,
    scrape_success_rate NUMERIC(5,2) CHECK (scrape_success_rate BETWEEN 0 AND 100),
    portal_coverage_score NUMERIC(5,2) CHECK (portal_coverage_score BETWEEN 0 AND 100),
    -- Official portal details
    official_career_portal_domain TEXT,
    official_career_portal_base_url TEXT,
    official_source_flag BOOLEAN DEFAULT TRUE,
    -- Freshness / timing
    latest_scrape_timestamp TIMESTAMPTZ,
    earliest_job_posted_date DATE,
    latest_job_posted_date DATE,
    latest_job_updated_date DATE,
    average_posting_age_days NUMERIC(8,2),
    median_posting_age_days NUMERIC(8,2),
    -- Trend fields
    trend_30d_pct NUMERIC(8,2),
    trend_90d_pct NUMERIC(8,2),
    hiring_trend_label TEXT,
    -- Job content fields
    sample_job_titles TEXT[],
    sample_requisition_ids TEXT[],
    sample_job_urls TEXT[],
    dominant_skills TEXT[],
    delivery_model_tags TEXT[],
    employment_type_tags TEXT[],
    work_mode_tags TEXT[],
    -- NLP / ML-friendly fields
    extracted_skills JSONB DEFAULT '[]'::JSONB,
    seniority_distribution JSONB DEFAULT '{}'::JSONB,
    geography_distribution JSONB DEFAULT '{}'::JSONB,
    capability_distribution JSONB DEFAULT '{}'::JSONB,
    job_family_distribution JSONB DEFAULT '{}'::JSONB,
    feature_vector JSONB DEFAULT '{}'::JSONB,
    -- Source quality / confidence
    deduplication_method TEXT,
    source_quality_score NUMERIC(4,3) CHECK (source_quality_score BETWEEN 0 AND 1),
    confidence_score NUMERIC(4,3) CHECK (confidence_score BETWEEN 0 AND 1),
    data_completeness_score NUMERIC(4,3) CHECK (data_completeness_score BETWEEN 0 AND 1),
    source_limitations TEXT,
    -- LLM evidence / narrative context
    llm_context TEXT,
    llm_summary TEXT,
    evidence_items JSONB DEFAULT '[]'::JSONB,
    source_urls JSONB DEFAULT '[]'::JSONB,
    -- Audit fields
    methodology_version TEXT DEFAULT 'mvp_v1',
    ingestion_run_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
-- ============================================================
-- 3. SHARE OF VOICE
-- Grain: one row per firm-theme-region-period
-- Purpose: public-source visibility by firm and risk theme
-- ============================================================
create table if not exists share_of_voice (
    id BIGSERIAL PRIMARY KEY,
    analysis_period_start DATE NOT NULL,
    analysis_period_end DATE NOT NULL,
    firm_name TEXT NOT NULL,
    theme_name TEXT NOT NULL,
    region TEXT DEFAULT 'Global',
    firm_mention_count INTEGER DEFAULT 0,
    total_market_mention_count INTEGER DEFAULT 0,
    share_of_voice_pct NUMERIC(6,2) CHECK (share_of_voice_pct BETWEEN 0 AND 100),
    source_quality_adjusted_sov_pct NUMERIC(6,2) CHECK (source_quality_adjusted_sov_pct BETWEEN 0 AND 100),
    rank_by_theme INTEGER,
    official_source_mentions INTEGER DEFAULT 0,
    media_mentions INTEGER DEFAULT 0,
    linkedin_mentions INTEGER DEFAULT 0,
    thought_leadership_mentions INTEGER DEFAULT 0,
    job_posting_mentions INTEGER DEFAULT 0,
    weighted_mention_score NUMERIC(10,2),
    prominence_score NUMERIC(5,2) CHECK (prominence_score BETWEEN 0 AND 100),
    sentiment_score NUMERIC(5,2),
    top_keywords TEXT[],
    sample_headlines TEXT[],
    mention_breakdown JSONB DEFAULT '{}'::JSONB,
    source_mix JSONB DEFAULT '{}'::JSONB,
    feature_vector JSONB DEFAULT '{}'::JSONB,
    llm_context TEXT,
    llm_summary TEXT,
    evidence_items JSONB DEFAULT '[]'::JSONB,
    source_urls JSONB DEFAULT '[]'::JSONB,
    confidence_score NUMERIC(4,3) CHECK (confidence_score BETWEEN 0 AND 1),
    source_quality_score NUMERIC(4,3) CHECK (source_quality_score BETWEEN 0 AND 1),
    methodology_version TEXT DEFAULT 'mvp_v1',
    ingestion_run_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
-- ============================================================
-- 4. DEAL & ALLIANCE ACTIVITY TRACKER
-- Grain: one row per observable public activity/event
-- Purpose: track acquisitions, alliances, platforms, senior hires, etc.
-- ============================================================
create table if not exists deal_alliance_activity_tracker (
    id BIGSERIAL PRIMARY KEY,
    event_date DATE,
    announcement_date DATE,
    analysis_period_start DATE,
    analysis_period_end DATE,
    firm_name TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    activity_subtype TEXT,
    target_or_partner_name TEXT,
    target_or_partner_type TEXT,
    region TEXT DEFAULT 'Global',
    country TEXT,
    city TEXT,
    risk_theme TEXT,
    sector_focus TEXT,
    capability_area TEXT,
    event_title TEXT,
    event_description TEXT,
    deal_value NUMERIC(18,2),
    deal_value_currency TEXT,
    strategic_signal_score NUMERIC(5,2) CHECK (strategic_signal_score BETWEEN 0 AND 100),
    relevance_to_risk_practice_score NUMERIC(5,2) CHECK (relevance_to_risk_practice_score BETWEEN 0 AND 100),
    market_impact_score NUMERIC(5,2) CHECK (market_impact_score BETWEEN 0 AND 100),
    is_acquisition BOOLEAN DEFAULT FALSE,
    is_alliance BOOLEAN DEFAULT FALSE,
    is_platform_launch BOOLEAN DEFAULT FALSE,
    is_regional_expansion BOOLEAN DEFAULT FALSE,
    is_senior_hire BOOLEAN DEFAULT FALSE,
    is_public_client_win BOOLEAN DEFAULT FALSE,
    official_source_flag BOOLEAN DEFAULT FALSE,
    public_information_only_flag BOOLEAN DEFAULT TRUE,
    event_tags TEXT[],
    affected_capabilities TEXT[],
    activity_metadata JSONB DEFAULT '{}'::JSONB,
    feature_vector JSONB DEFAULT '{}'::JSONB,
    llm_context TEXT,
    llm_summary TEXT,
    evidence_items JSONB DEFAULT '[]'::JSONB,
    source_urls JSONB DEFAULT '[]'::JSONB,
    confidence_score NUMERIC(4,3) CHECK (confidence_score BETWEEN 0 AND 1),
    source_quality_score NUMERIC(4,3) CHECK (source_quality_score BETWEEN 0 AND 1),
    methodology_version TEXT DEFAULT 'mvp_v1',
    ingestion_run_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
-- ============================================================
-- INDEXES
-- ============================================================
-- 1. Momentum
create index if not exists idx_momentum_period
on risk_practice_momentum_index
(analysis_period_start, analysis_period_end);

create index if not exists idx_momentum_firm
on risk_practice_momentum_index
(firm_name);

create index if not exists idx_momentum_score
on risk_practice_momentum_index
(momentum_score DESC);

create index if not exists idx_momentum_evidence_gin
on risk_practice_momentum_index
using GIN (evidence_items);


-- 2. Hiring
create index if not exists idx_hiring_period_firm
on hiring_intensity_index
(analysis_period_start, analysis_period_end, firm_name);

create index if not exists idx_hiring_region_theme
on hiring_intensity_index
(region, risk_capability_theme);

create index if not exists idx_hiring_score
on hiring_intensity_index
(hiring_intensity_score DESC);

create index if not exists idx_hiring_evidence_gin
on hiring_intensity_index
using GIN (evidence_items);


-- 3. Share of Voice
create index if not exists idx_sov_period_theme
on share_of_voice
(analysis_period_start, analysis_period_end, theme_name);

create index if not exists idx_sov_firm_region
on share_of_voice
(firm_name, region);

create index if not exists idx_sov_pct
on share_of_voice
(share_of_voice_pct DESC);

create index if not exists idx_sov_evidence_gin
on share_of_voice
using GIN (evidence_items);

-- 5. Deal & Alliance Activity
create index if not exists idx_deal_firm_event_date
on deal_alliance_activity_tracker
(firm_name, event_date DESC);

create index if not exists idx_deal_activity_type
on deal_alliance_activity_tracker
(activity_type, activity_subtype);

create index if not exists idx_deal_region_theme
on deal_alliance_activity_tracker
(region, risk_theme);

create index if not exists idx_deal_evidence_gin
on deal_alliance_activity_tracker
using GIN (evidence_items);
-- ============================================================
-- TEST SCRIPTS
-- ============================================================
select * from information_schema.tables where table_schema = 'public';
select * from share_of_voice;
select * from risk_practice_momentum_index;
select * from hiring_intensity_index;
select * from deal_alliance_activity_tracker;

delete from risk_practice_momentum_index where firm_name in ('mckinsey', 'bain', 'boston consulting', 'accenture'); 