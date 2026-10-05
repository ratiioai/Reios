-- PostgreSQL Database Setup for Coding Test Platform
-- Run this file to create the database and user

-- Create database
CREATE DATABASE coding_test_db;

-- Create user with password
CREATE USER coding_test_user WITH PASSWORD 'test123';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE coding_test_db TO coding_test_user;

-- Connect to the database
\c coding_test_db

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO coding_test_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO coding_test_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO coding_test_user;

-- Success message
\echo 'Database setup complete!'
\echo 'Database: coding_test_db'
\echo 'User: coding_test_user'
\echo 'Password: test123'
