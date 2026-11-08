import { useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Alert, Button, Card, Flex, Spin, Tabs, Tag, Typography } from "antd";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { Button as MButton, CapsuleTabs, DotLoading, ErrorBlock } from "antd-mobile";

import { useT } from "../../i18n/I18n";
import { useIsMobile } from "../../components/responsive";
import { useErrorMessage } from "../../components/errors";
import { useAnimal, useReprodutivo, type Animal } from "./api";
import { TagReprodutivo } from "../../components/EstadoReprodutivo";
import { RegistarSaida } from "../estadias/EstadiasPage";
import type { Estadia } from "../estadias/api";
import { ResumoTab } from "./ResumoTab";
import { RegistoClinico } from "./RegistoClinico";
import { AlertasTab, EstadiasAnimalTab, FertilidadeTab, ProducaoTab, ReprodutivoTab } from "./OutrosTabs";

/** Separadores da ficha — como a app atual, variam com o tipo do animal. */
function separadores(animal: Animal) {
  if (animal.tipo === "garanhao")
    return [
      { id: "resumo", label: "web.animal.tab.summary", el: <ResumoTab animal={animal} /> },
      { id: "producao", label: "web.animal.tab.production", el: <ProducaoTab animal={animal} /> },
      { id: "fertilidade", label: "web.animal.tab.fertility", el: <FertilidadeTab animal={animal} /> },
      { id: "alertas", label: "web.animal.tab.alerts", el: <AlertasTab animal={animal} /> },
    ];
  return [
    { id: "resumo", label: "web.animal.tab.summary", el: <ResumoTab animal={animal} /> },
    { id: "diario", label: "web.animal.tab.clinical", el: <RegistoClinico animal={animal} /> },
    { id: "reprodutivo", label: "web.animal.tab.reproductive", el: <ReprodutivoTab animal={animal} /> },
    { id: "estadias", label: "web.animal.tab.stays", el: <EstadiasAnimalTab animal={animal} /> },
  ];
}

/** Ficha do animal — equivalente a `animal_page.py`. */
export function AnimalPage() {
  const t = useT();
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const errorMessage = useErrorMessage();
  const id = Number(useParams().id);
  const [params, setParams] = useSearchParams();
  const q = useAnimal(id);
  const animal = q.data;
  // Estado reprodutivo à vista (a pergunta do dono, sem abrir o historial).
  const ultima = useReprodutivo(id).data?.inseminacoes[0];
  // Registar saída também a partir da ficha (no telemóvel só havia o deslizar na lista).
  const [saida, setSaida] = useState<Estadia | null>(null);

  if (q.isError)
    return isMobile ? (
      <ErrorBlock status="empty" title={errorMessage(q.error)} description="" />
    ) : (
      <Alert type="error" showIcon title={errorMessage(q.error)} />
    );
  if (!animal)
    return isMobile ? (
      <div style={{ textAlign: "center", padding: 48 }}>
        <DotLoading color="primary" />
      </div>
    ) : (
      <Spin style={{ display: "block", margin: 48 }} />
    );

  const tabs = separadores(animal);
  const tab = tabs.find((x) => x.id === params.get("tab"))?.id ?? "resumo";
  const mudar = (v: string) => setParams((p) => (v === "resumo" ? p.delete("tab") : p.set("tab", v), p), { replace: true });
  const etiquetas = (
    <>
      <Tag>{t(`web.stays.animal.${animal.tipo}`)}</Tag>
      {animal.estadia_ativa !== null && <Tag color="blue">{t("web.stays.in_clinic")}</Tag>}
      {animal.tipo !== "garanhao" && ultima && (
        <TagReprodutivo
          r={{ data_inseminacao: ultima.data_inseminacao, resultado: ultima.resultado, ultimo_dg: ultima.ultimo_dg }}
        />
      )}
    </>
  );

  const abrirSaida = () => {
    if (animal.estadia_ativa !== null) setSaida({ id: animal.estadia_ativa, animal: animal.nome } as Estadia);
  };
  const botaoSaida =
    animal.estadia_ativa !== null &&
    (isMobile ? (
      <MButton size="small" fill="outline" style={{ margin: "4px 0 8px" }} onClick={abrirSaida}>
        {t("web.stays.register_exit")}
      </MButton>
    ) : (
      <Button onClick={abrirSaida}>{t("web.stays.register_exit")}</Button>
    ));
  const janelaSaida = <RegistarSaida estadia={saida} onClose={() => setSaida(null)} />;

  if (isMobile)
    return (
      <>
        {janelaSaida}
        <div style={{ background: "#fff", padding: "10px 12px 0" }}>
          <div style={{ fontSize: 17, fontWeight: 700 }}>{animal.nome}</div>
          <div style={{ margin: "4px 0 2px" }}>{etiquetas}</div>
          {botaoSaida}
        </div>
        <CapsuleTabs activeKey={tab} onChange={mudar} style={{ background: "#fff" }}>
          {tabs.map((x) => (
            <CapsuleTabs.Tab key={x.id} title={t(x.label)} />
          ))}
        </CapsuleTabs>
        {tabs.find((x) => x.id === tab)!.el}
      </>
    );

  return (
    <Card size="small">
      {janelaSaida}
      <Button type="link" icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)} style={{ paddingInline: 0 }}>
        {t("web.common.back")}
      </Button>
      <Flex align="center" gap={10} wrap>
        <Typography.Title level={4} style={{ margin: 0 }}>
          {animal.nome}
        </Typography.Title>
        {etiquetas}
        <div style={{ marginLeft: "auto" }}>{botaoSaida}</div>
      </Flex>
      <Tabs activeKey={tab} onChange={mudar} destroyOnHidden items={tabs.map((x) => ({ key: x.id, label: t(x.label), children: x.el }))} />
    </Card>
  );
}
