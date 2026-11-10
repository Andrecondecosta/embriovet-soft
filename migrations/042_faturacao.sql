-- 042: Faturação (estadias e armazenamento de sémen). A app não emite
-- faturas: conta os dias / palhetas × dias e regista o que já foi faturado
-- (número e data da fatura do programa de faturação), para nada ser
-- faturado duas vezes nem ficar esquecido. Só acrescenta.
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS acesso_faturacao BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS faturacao_linhas (
    id SERIAL PRIMARY KEY,
    tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('estadia', 'armazenamento')),
    -- estadias.id ou estoque_dono.id. Sem chave estrangeira: o que foi
    -- faturado fica, mesmo que a estadia ou o lote venham a ser apagados.
    ref_id INTEGER NOT NULL,
    dono_id INTEGER,
    dono_nome VARCHAR(255),
    descricao TEXT NOT NULL,
    inicio DATE NOT NULL,
    fim DATE NOT NULL CHECK (fim >= inicio),
    -- Estadia: dias. Sémen: palhetas × dias (e `palhetas` = as do troço).
    quantidade INTEGER NOT NULL,
    palhetas INTEGER,
    fatura_numero VARCHAR(60) NOT NULL,
    fatura_data DATE NOT NULL,
    observacoes TEXT,
    criado_por VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    anulada BOOLEAN NOT NULL DEFAULT FALSE,
    anulada_por VARCHAR(50),
    anulada_em TIMESTAMP,
    motivo_anulacao TEXT
);
CREATE INDEX IF NOT EXISTS idx_faturacao_ref ON faturacao_linhas (tipo, ref_id) WHERE NOT anulada;
CREATE INDEX IF NOT EXISTS idx_faturacao_fatura ON faturacao_linhas (fatura_numero);
