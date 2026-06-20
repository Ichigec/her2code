-- Schema for response_store.db
-- Extracted: 2026-06-19T20:37:55.351900

CREATE TABLE responses (
                response_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                accessed_at REAL NOT NULL
            );
CREATE TABLE conversations (
                name TEXT PRIMARY KEY,
                response_id TEXT NOT NULL
            );
