-- Runs once when the Postgres container is first created.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- fuzzy place-name search
