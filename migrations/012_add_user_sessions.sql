-- Tabela de sessões persistentes para manter login após refresh
CREATE TABLE IF NOT EXISTS user_sessions (
    token       TEXT PRIMARY KEY,
    username    TEXT NOT NULL,
    user_data   TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW(),
    expires_at  TIMESTAMP NOT NULL
);

-- Índice para limpeza de sessões expiradas
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires ON user_sessions (expires_at);
