BEGIN;

CREATE TABLE IF NOT EXISTS sites (
    site_id VARCHAR(128) PRIMARY KEY,
    display_name VARCHAR(255),
    parent_url TEXT,
    rules_version VARCHAR(64),
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS site_styles (
    site_id VARCHAR(128) PRIMARY KEY REFERENCES sites(site_id) ON DELETE CASCADE,
    css TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS site_pages (
    id SERIAL PRIMARY KEY,
    site_id VARCHAR(128) NOT NULL REFERENCES sites(site_id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_crawled_at TIMESTAMPTZ,
    meta JSONB,
    content_hash TEXT,
    info_last_refreshed_at TIMESTAMPTZ,
    atlas_last_refreshed_at TIMESTAMPTZ,
    embeddings_last_refreshed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_site_pages_site_url UNIQUE(site_id, url)
);
CREATE INDEX IF NOT EXISTS ix_site_pages_site_status ON site_pages(site_id, status);

CREATE TABLE IF NOT EXISTS rules (
    id VARCHAR(96) PRIMARY KEY,
    site_id VARCHAR(128) NOT NULL REFERENCES sites(site_id) ON DELETE CASCADE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    tracking BOOLEAN NOT NULL DEFAULT TRUE,
    rule_instruction TEXT NOT NULL,
    output_instruction TEXT,
    triggers JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_rules_site_id ON rules(site_id);

CREATE TABLE IF NOT EXISTS site_info (
    id SERIAL PRIMARY KEY,
    site_id VARCHAR(128) NOT NULL REFERENCES sites(site_id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    meta JSONB,
    normalized JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_site_info_site_url UNIQUE(site_id, url)
);
CREATE INDEX IF NOT EXISTS ix_site_info_site_id ON site_info(site_id);

CREATE TABLE IF NOT EXISTS site_map_pages (
    id SERIAL PRIMARY KEY,
    site_id VARCHAR(128) NOT NULL REFERENCES sites(site_id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    meta JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_site_map_site_url UNIQUE(site_id, url)
);
CREATE INDEX IF NOT EXISTS ix_site_map_pages_site_id ON site_map_pages(site_id);

CREATE TABLE IF NOT EXISTS site_embeddings (
    id SERIAL PRIMARY KEY,
    site_id VARCHAR(128) NOT NULL REFERENCES sites(site_id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    embedding JSONB NOT NULL,
    text TEXT NOT NULL,
    meta JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_site_embeddings_site_url UNIQUE(site_id, url)
);
CREATE INDEX IF NOT EXISTS ix_site_embeddings_site_id ON site_embeddings(site_id);

CREATE TABLE IF NOT EXISTS site_atlas (
    id SERIAL PRIMARY KEY,
    site_id VARCHAR(128) NOT NULL REFERENCES sites(site_id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    atlas JSONB,
    queued_plan_rebuild BOOLEAN,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_site_atlas_site_url UNIQUE(site_id, url)
);
CREATE INDEX IF NOT EXISTS ix_site_atlas_site_id ON site_atlas(site_id);

COMMIT;
