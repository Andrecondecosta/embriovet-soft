-- 048: Localização das éguas externas (acompanhadas em casa do cliente):
-- o sítio em texto e, se se quiser, o ponto no mapa (coordenadas "lat,lng"
-- ou um link do Google Maps). Fica na entrada (estadias). Só acrescenta.
ALTER TABLE estadias ADD COLUMN IF NOT EXISTS localizacao TEXT;
ALTER TABLE estadias ADD COLUMN IF NOT EXISTS localizacao_mapa TEXT;
