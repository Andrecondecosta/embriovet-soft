-- ================================================
-- CRIAR TABELA DE UTILIZADORES E AUTENTICAÇÃO
-- ================================================

CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    nome_completo VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nivel VARCHAR(50) NOT NULL CHECK (nivel IN ('Administrador', 'Gestor', 'Visualizador')),
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    created_by INTEGER REFERENCES usuarios(id) ON DELETE SET NULL
);

COMMENT ON TABLE usuarios IS 'Utilizadores do sistema com diferentes níveis de acesso';
COMMENT ON COLUMN usuarios.username IS 'Nome de utilizador único para login';
COMMENT ON COLUMN usuarios.nome_completo IS 'Nome completo do utilizador';
COMMENT ON COLUMN usuarios.password_hash IS 'Hash da password (bcrypt)';
COMMENT ON COLUMN usuarios.nivel IS 'Nível de acesso: Administrador, Gestor ou Visualizador';
COMMENT ON COLUMN usuarios.ativo IS 'Se o utilizador está ativo ou desativado';
COMMENT ON COLUMN usuarios.created_by IS 'Quem criou este utilizador';

-- Criar índices
CREATE INDEX IF NOT EXISTS idx_usuarios_username ON usuarios(username);
CREATE INDEX IF NOT EXISTS idx_usuarios_nivel ON usuarios(nivel);
CREATE INDEX IF NOT EXISTS idx_usuarios_ativo ON usuarios(ativo);

-- Inserir utilizador ADMINISTRADOR INICIAL
-- Username: admin
-- Password: admin123
-- IMPORTANTE: MUDAR A PASSWORD DEPOIS DO PRIMEIRO LOGIN!

INSERT INTO usuarios (username, nome_completo, password_hash, nivel, ativo)
VALUES (
    'admin',
    'Administrador',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYsP8f3glK.',  -- password: admin123
    'Administrador',
    TRUE
) ON CONFLICT (username) DO NOTHING;

-- Verificar
SELECT 'Tabela de utilizadores criada!' as status;
SELECT * FROM usuarios;

-- ================================================
-- CREDENCIAIS INICIAIS
-- ================================================
-- Username: admin
-- Password: admin123
-- 
-- ⚠️ IMPORTANTE: Altere a password após o primeiro login!
-- ================================================
