-- Run as a PostgreSQL superuser (usually `postgres`), e.g.:
--   psql -h localhost -p 5432 -U postgres -d postgres -f scripts/reset_local_postgres.sql
-- Or open `psql` and paste this file after editing YOUR_PASSWORD.
--
-- Picks a new app role + database for local dev. Replace YOUR_PASSWORD before running.

-- Close other sessions on these DBs (ignore errors if DBs do not exist).
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname IN ('writers_ai', 'writers_ai_memory') AND pid <> pg_backend_pid();

DROP DATABASE IF EXISTS writers_ai;
DROP DATABASE IF EXISTS writers_ai_memory;
DROP ROLE IF EXISTS writers_app;

CREATE ROLE writers_app WITH LOGIN PASSWORD '123456';

CREATE DATABASE writers_ai_memory OWNER writers_app;
