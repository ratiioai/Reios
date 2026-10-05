-- Create database
CREATE DATABASE coding_test_db;

-- Create user
CREATE USER coding_test_user WITH PASSWORD 'test123';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE coding_test_db TO coding_test_user;

-- Connect to the new database
\c coding_test_db

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO coding_test_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO coding_test_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO coding_test_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO coding_test_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO coding_test_user;
