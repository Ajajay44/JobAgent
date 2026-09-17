-- ─────────────────────────────────────────────────────────────────────────
-- PostgreSQL initialization script
-- Run automatically by Docker on first container start.
-- ─────────────────────────────────────────────────────────────────────────

-- Enable pgvector extension.
-- This allows storing and querying vector embeddings directly in PostgreSQL.
-- Used for company research RAG (Phase 5).
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify installation
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE NOTICE 'pgvector extension installed successfully.';
    ELSE
        RAISE EXCEPTION 'pgvector extension installation FAILED.';
    END IF;
END $$;
