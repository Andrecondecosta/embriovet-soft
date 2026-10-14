import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Anchor, NumberInput, Paper, SimpleGrid, Stack, TextInput, Title } from "@mantine/core";
import { IconArrowLeft } from "@tabler/icons-react";

import { useT } from "../../i18n/I18n";
import { useIsMobile } from "../../components/responsive";
import { notifySuccess, useNotifyError } from "../../components/errors";
import { useCriarLote, type LoteCampos, type LoteNovo } from "./api";
import { BotoesForm, CamposLote, DonoSelect, GaranhaoInput, Secao, camposVazios } from "./LoteForm";

/** "Adicionar lote" — equivalente a `add_stock_view.py`. O garanhão pode
 *  ser escolhido da lista ou escrito de novo: o servidor cria-o em
 *  `animais` (`get_or_create_garanhao`), sem duplicar "Falcao"/"Falcão". */
export function AddLotePage() {
  const t = useT();
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const notifyError = useNotifyError();
  const [params] = useSearchParams();
  const criar = useCriarLote();

  const [dados, setDados] = useState<LoteNovo>(() => ({
    ...camposVazios(),
    garanhao: params.get("garanhao") ?? "",
    palhetas: 0,
  }));
  const [erros, setErros] = useState<Partial<Record<keyof LoteCampos | "palhetas", string>>>({});
  const set = (patch: Partial<LoteNovo>) => {
    setDados((d) => ({ ...d, ...patch }));
    // O erro de um campo desaparece logo que o campo é alterado.
    setErros((e) => Object.fromEntries(Object.entries(e).filter(([k]) => !(k in patch))));
  };


  const voltar = () => navigate(-1);

  const submeter = async (e: FormEvent) => {
    e.preventDefault();
    const novos: typeof erros = {};
    if (!dados.garanhao.trim()) novos.garanhao = t("error.stallion_required");
    if (!dados.dono_id) novos.dono_id = t("web.stock.error.owner_required");
    if (!dados.contentor_id) novos.contentor_id = t("error.container_required");
    if (!(dados.palhetas > 0)) novos.palhetas = t("error.straws_positive");
    setErros(novos);
    if (Object.keys(novos).length) {
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    try {
      const lote = await criar.mutateAsync(dados);
      notifySuccess(t("web.stock.added"));
      // Como na app atual: volta aos Lotes, no garanhão do lote novo, com
      // o lote aberto.
      navigate(
        `/stock-semen/lotes?garanhao=${encodeURIComponent(lote.garanhao_nome)}&lote=${lote.id}`,
        { replace: true },
      );
    } catch (err) {
      notifyError(err);
    }
  };

  return (
    <Stack gap="md" maw={960}>
      <Anchor component="button" type="button" onClick={voltar} size="sm" c="dimmed" style={{ alignSelf: "flex-start" }}>
        <IconArrowLeft size={14} style={{ verticalAlign: -2, marginRight: 4 }} />
        {t("web.stock.back")}
      </Anchor>
      <Title order={2}>{t("web.stock.add")}</Title>

      <Paper withBorder radius="lg" p={{ base: "md", sm: "xl" }} component="form" onSubmit={submeter}>
        <Stack gap="lg">
          <Secao titulo={t("web.stock.add.identification")}>
            <SimpleGrid cols={{ base: 1, sm: 2 }}>
              <GaranhaoInput
                value={dados.garanhao}
                onChange={(v) => set({ garanhao: v })}
                error={erros.garanhao}
                autoFocus={!isMobile}
              />
              <DonoSelect
                label={t("add_stock.owner_semen").replace(" *", "")}
                apenasAtivos={false}
                value={dados.dono_id}
                onChange={(id) => set({ dono_id: id })}
                error={erros.dono_id}
              />
            </SimpleGrid>
          </Secao>

          <CamposLote
            dados={dados}
            set={set}
            erros={erros}
            producao={
              <SimpleGrid cols={{ base: 1, xs: 3 }}>
                <TextInput label={t("stock.prod_date")} value={dados.data_embriovet} onChange={(e) => set({ data_embriovet: e.currentTarget.value })} />
                <NumberInput
                  label={t("stock.straws_produced")}
                  withAsterisk
                  min={0}
                  value={dados.palhetas}
                  onChange={(v) => set({ palhetas: Number(v) || 0 })}
                  error={erros.palhetas}
                  inputMode="numeric"
                />
                <TextInput label={t("stock.external_origin")} value={dados.origem_externa} onChange={(e) => set({ origem_externa: e.currentTarget.value })} />
              </SimpleGrid>
            }
          />

          <BotoesForm isMobile={isMobile} onCancel={voltar} loading={criar.isPending} label={t("btn.save")} />
        </Stack>
      </Paper>
    </Stack>
  );
}
