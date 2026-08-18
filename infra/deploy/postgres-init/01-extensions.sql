-- Enable pgvector on first cluster init (empty data volume). The pgvector image
-- already bundles the extension, so this just activates it.
CREATE EXTENSION IF NOT EXISTS vector;
