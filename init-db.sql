-- Initialize database with pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Set default search path
ALTER DATABASE omnisift SET search_path = public;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE omnisift TO omnisift;
GRANT ALL ON SCHEMA public TO omnisift;