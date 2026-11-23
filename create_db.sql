-- Run by setup.ps1 as the postgres superuser (local install without Docker).
-- Variables: db_name, db_user, db_password (taken from .env)

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'db_user', :'db_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'db_user') \gexec

SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'db_user', :'db_password') \gexec

SELECT format('CREATE DATABASE %I OWNER %I ENCODING %L TEMPLATE template0', :'db_name', :'db_user', 'UTF8')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db_name') \gexec
