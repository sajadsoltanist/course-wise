-- CourseWise Database Initialization Script
-- This script runs automatically when the PostgreSQL container starts

-- Create extensions that might be useful
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Set timezone
SET timezone = 'UTC';

-- Ensure proper encoding
SET client_encoding = 'UTF8';

-- Create any additional roles or permissions if needed
-- (Currently using default coursewise user)