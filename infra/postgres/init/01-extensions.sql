-- Runs once on first cluster init (empty data volume).
-- pgvector ships in the pgvector/pgvector image; enable it for embedding columns.
CREATE EXTENSION IF NOT EXISTS vector;
