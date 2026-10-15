import { useEffect, useRef, useState } from "react";
import { Alert, Button, Col, ColorPicker, Flex, Input, Radio, Row, Space, Spin, Typography } from "antd";
import { DeleteOutlined, UploadOutlined } from "@ant-design/icons";
import { Button as MButton, CheckList, Dialog, DotLoading, Input as MInput, List } from "antd-mobile";

import { useT } from "../../i18n/I18n";
import { useIsMobile } from "../../components/responsive";
import { confirmar, notifySuccess, useNotifyError } from "../../components/errors";
import { Cabecalho } from "../../components/mobile";
import { IDIOMAS, useGravarMarca, useMarca, useReporMarca, type Marca } from "./api";

/** Cores para escolher depressa (a primeira é a de origem). */
const CORES = ["#E85D4A", "#1677FF", "#13A8A8", "#52C41A", "#FA8C16", "#722ED1", "#EB2F96", "#262626"];
const LOGO_MAX_BYTES = 1_000_000;
/** O logótipo aparece pequeno (menu, login): reduz-se antes de gravar. */
const LOGO_MAX_PX = 400;

/** Lê uma imagem escolhida e devolve um data URI PNG/JPEG (reduzido se for grande). */
function lerLogo(ficheiro: File): Promise<string> {
  return new Promise((resolve, reject) => {
    if (!/^image\/(png|jpe?g)$/.test(ficheiro.type)) return reject(new Error("web.settings.error.logo_type"));
    if (ficheiro.size > 8 * LOGO_MAX_BYTES) return reject(new Error("web.settings.error.logo_size"));
    const leitor = new FileReader();
    leitor.onerror = () => reject(new Error("web.settings.error.logo_type"));
    leitor.onload = () => {
      const uri = String(leitor.result);
      const img = new Image();
      img.onerror = () => reject(new Error("web.settings.error.logo_type"));
      img.onload = () => {
        const escala = Math.min(1, LOGO_MAX_PX / Math.max(img.width, img.height));
        if (escala === 1 && uri.length <= LOGO_MAX_BYTES) return resolve(uri);
        const canvas = document.createElement("canvas");
        canvas.width = Math.round(img.width * escala);
        canvas.height = Math.round(img.height * escala);
        canvas.getContext("2d")!.drawImage(img, 0, 0, canvas.width, canvas.height);
        const reduzido = canvas.toDataURL(ficheiro.type === "image/png" ? "image/png" : "image/jpeg", 0.9);
        if (reduzido.length > LOGO_MAX_BYTES) return reject(new Error("web.settings.error.logo_size"));
        resolve(reduzido);
      };
      img.src = uri;
    };
    leitor.readAsDataURL(ficheiro);
  });
}

/** Estado do formulário da marca + gravar/repor — comum ao computador e ao telemóvel. */
function useFormMarca() {
  const t = useT();
  const notifyError = useNotifyError();
  const marca = useMarca();
  const gravar = useGravarMarca();
  const repor = useReporMarca();
  const [form, setForm] = useState<Marca | null>(null);
  const [erroLogo, setErroLogo] = useState<string | null>(null);
  useEffect(() => {
    if (marca.data && !form) setForm(marca.data);
  }, [marca.data, form]);

  const mudar = (p: Partial<Marca>) => setForm((f) => (f ? { ...f, ...p } : f));
  const escolherLogo = async (f: File | undefined) => {
    if (!f) return;
    setErroLogo(null);
    try {
      mudar({ logo_base64: await lerLogo(f) });
    } catch (e) {
      setErroLogo(t((e as Error).message));
    }
  };
  const guardar = async () => {
    if (!form) return;
    try {
      setForm(await gravar.mutateAsync(form));
      notifySuccess(t("web.settings.saved"));
    } catch (err) {
      notifyError(err);
    }
  };
  const fazerRepor = async () => {
    try {
      setForm(await repor.mutateAsync());
      notifySuccess(t("web.settings.restored"));
    } catch (err) {
      notifyError(err);
    }
  };
  const alterado = !!form && !!marca.data && JSON.stringify(form) !== JSON.stringify(marca.data);
  return { form, mudar, escolherLogo, erroLogo, guardar, aGuardar: gravar.isPending, fazerRepor, alterado };
}

/** Escolher ficheiro de imagem com um botão próprio. */
function useEscolherFicheiro(onFicheiro: (f: File | undefined) => void) {
  const ref = useRef<HTMLInputElement>(null);
  const input = (
    <input
      ref={ref}
      type="file"
      accept="image/png,image/jpeg"
      hidden
      onChange={(e) => {
        onFicheiro(e.target.files?.[0]);
        e.target.value = "";
      }}
    />
  );
  return { input, abrir: () => ref.current?.click() };
}

/** Pré-visualização do menu com a marca escolhida. */
function Previsao({ m }: { m: Marca }) {
  const iniciais = m.company_name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
  return (
    <div style={{ background: "#001529", borderRadius: 8, padding: 14, color: "#fff", width: "100%", maxWidth: 260 }}>
      <Flex gap={10} align="center" style={{ marginBottom: 14 }}>
        {m.logo_base64 ? (
          <img src={m.logo_base64} alt="" style={{ width: 32, height: 32, objectFit: "contain", borderRadius: 6, background: "#fff" }} />
        ) : (
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 6,
              background: m.primary_color,
              display: "grid",
              placeItems: "center",
              fontWeight: 700,
            }}
          >
            {iniciais || "?"}
          </div>
        )}
        <b style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.company_name || "—"}</b>
      </Flex>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            height: 26,
            borderRadius: 6,
            marginBottom: 6,
            background: i === 0 ? m.primary_color : "rgba(255,255,255,.08)",
          }}
        />
      ))}
    </div>
  );
}

export function MarcaTab() {
  return useIsMobile() ? <MarcaMobile /> : <MarcaDesktop />;
}

function MarcaDesktop() {
  const t = useT();
  const { form, mudar, escolherLogo, erroLogo, guardar, aGuardar, fazerRepor, alterado } = useFormMarca();
  const ficheiro = useEscolherFicheiro(escolherLogo);
  if (!form) return <Spin style={{ display: "block", margin: 32 }} />;

  return (
    <Row gutter={[32, 16]}>
      <Col xs={24} md={14}>
        <Space orientation="vertical" size={16} style={{ width: "100%", maxWidth: 460 }}>
          <Typography.Text type="secondary">{t("web.settings.brand.help")}</Typography.Text>
          <div>
            <Typography.Text strong>{t("label.company_name")}</Typography.Text>
            <Input value={form.company_name} onChange={(e) => mudar({ company_name: e.target.value })} maxLength={80} />
          </div>
          <div>
            <Typography.Text strong style={{ display: "block" }}>
              {t("label.logo")}
            </Typography.Text>
            <Flex gap={8} align="center" wrap>
              {form.logo_base64 && (
                <img
                  src={form.logo_base64}
                  alt=""
                  style={{ height: 40, maxWidth: 120, objectFit: "contain", border: "1px solid #f0f0f0", borderRadius: 6 }}
                />
              )}
              <Button icon={<UploadOutlined />} onClick={ficheiro.abrir}>
                {t("web.settings.brand.logo_choose")}
              </Button>
              {form.logo_base64 && (
                <Button type="text" danger icon={<DeleteOutlined />} onClick={() => mudar({ logo_base64: null })}>
                  {t("web.settings.brand.logo_remove")}
                </Button>
              )}
              {ficheiro.input}
            </Flex>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {t("web.settings.brand.logo_hint")}
            </Typography.Text>
            {erroLogo && <Alert type="error" showIcon title={erroLogo} style={{ marginTop: 6 }} />}
          </div>
          <div>
            <Typography.Text strong style={{ display: "block" }}>
              {t("web.settings.brand.color")}
            </Typography.Text>
            <ColorPicker
              value={form.primary_color}
              onChangeComplete={(c) => mudar({ primary_color: c.toHexString().toUpperCase() })}
              disabledAlpha
              showText
              presets={[{ label: "", colors: CORES }]}
            />
          </div>
          <Flex gap={8}>
            <Button type="primary" onClick={guardar} loading={aGuardar} disabled={!alterado}>
              {t("btn.save_changes")}
            </Button>
            <Button
              onClick={() =>
                confirmar({
                  titulo: t("web.settings.restore"),
                  texto: t("web.settings.brand.restore_confirm"),
                  ok: t("web.settings.restore"),
                  cancelar: t("web.common.cancel"),
                  onOk: fazerRepor,
                })
              }
            >
              {t("web.settings.restore")}
            </Button>
          </Flex>
        </Space>
      </Col>
      <Col xs={24} md={10}>
        <Typography.Text type="secondary" style={{ display: "block", marginBottom: 8 }}>
          {t("common.preview")}
        </Typography.Text>
        <Previsao m={form} />
      </Col>
    </Row>
  );
}

function MarcaMobile() {
  const t = useT();
  const { form, mudar, escolherLogo, erroLogo, guardar, aGuardar, fazerRepor, alterado } = useFormMarca();
  const ficheiro = useEscolherFicheiro(escolherLogo);
  if (!form)
    return (
      <div style={{ textAlign: "center", padding: 32 }}>
        <DotLoading color="primary" />
      </div>
    );

  return (
    <>
      <div style={{ padding: "10px 12px", color: "#999", fontSize: 12 }}>{t("web.settings.brand.help")}</div>
      <List style={{ "--prefix-width": "7.5em" } as React.CSSProperties}>
        <List.Item prefix={t("label.company_name")}>
          <MInput value={form.company_name} onChange={(v) => mudar({ company_name: v })} maxLength={80} clearable />
        </List.Item>
        <List.Item
          prefix={t("label.logo").replace(/\s*\(.*\)/, "")}
          description={erroLogo ? <span style={{ color: "var(--adm-color-danger)" }}>{erroLogo}</span> : t("web.settings.brand.logo_hint")}
          extra={
            form.logo_base64 && (
              <MButton size="mini" color="danger" fill="none" onClick={() => mudar({ logo_base64: null })}>
                {t("web.settings.brand.logo_remove")}
              </MButton>
            )
          }
          onClick={ficheiro.abrir}
          arrow={false}
        >
          {form.logo_base64 ? (
            <img src={form.logo_base64} alt="" style={{ height: 36, maxWidth: 110, objectFit: "contain" }} />
          ) : (
            <span style={{ color: "var(--adm-color-primary)" }}>{t("web.settings.brand.logo_choose")}</span>
          )}
          {ficheiro.input}
        </List.Item>
        <List.Item prefix={t("web.settings.brand.color")}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
            {CORES.map((c) => (
              <button
                key={c}
                type="button"
                aria-label={c}
                onClick={() => mudar({ primary_color: c })}
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: 14,
                  background: c,
                  border: "none",
                  outline: form.primary_color.toUpperCase() === c ? `2px solid ${c}` : "none",
                  outlineOffset: 2,
                  padding: 0,
                }}
              />
            ))}
            {/* Cor própria (formato #RRGGBB). */}
            <input
              type="color"
              value={form.primary_color}
              onChange={(e) => mudar({ primary_color: e.target.value.toUpperCase() })}
              style={{ width: 32, height: 28, border: "none", padding: 0, background: "none" }}
            />
          </div>
        </List.Item>
      </List>
      <Cabecalho>{t("common.preview")}</Cabecalho>
      <div style={{ padding: 12, display: "flex", justifyContent: "center" }}>
        <Previsao m={form} />
      </div>
      <div style={{ display: "flex", gap: 8, padding: 12 }}>
        <MButton
          block
          onClick={() =>
            void Dialog.confirm({
              title: t("web.settings.restore"),
              content: t("web.settings.brand.restore_confirm"),
              confirmText: t("web.settings.restore"),
              cancelText: t("web.common.cancel"),
              onConfirm: fazerRepor,
            })
          }
        >
          {t("web.settings.restore")}
        </MButton>
        <MButton block color="primary" loading={aGuardar} disabled={!alterado} onClick={guardar}>
          {t("btn.save")}
        </MButton>
      </div>
    </>
  );
}

/** Idioma da app (o mesmo para todos): grava logo ao escolher. */
export function IdiomaTab() {
  const t = useT();
  const isMobile = useIsMobile();
  const notifyError = useNotifyError();
  const marca = useMarca();
  const gravar = useGravarMarca();

  const escolher = async (language: string) => {
    if (!marca.data || language === marca.data.language) return;
    try {
      await gravar.mutateAsync({ ...marca.data, language });
      notifySuccess(t("settings.lang_updated"));
    } catch (err) {
      notifyError(err);
    }
  };

  if (!marca.data) return isMobile ? <DotLoading /> : <Spin style={{ display: "block", margin: 32 }} />;

  if (isMobile)
    return (
      <>
        <div style={{ padding: "10px 12px", color: "#999", fontSize: 12 }}>{t("web.settings.language.help")}</div>
        <CheckList value={[marca.data.language]} onChange={(v) => v[0] && escolher(String(v[0]))}>
          {IDIOMAS.map((i) => (
            <CheckList.Item key={i.value} value={i.value} disabled={gravar.isPending}>
              {i.label}
            </CheckList.Item>
          ))}
        </CheckList>
      </>
    );

  return (
    <Space orientation="vertical" size={12}>
      <Typography.Text type="secondary">{t("web.settings.language.help")}</Typography.Text>
      <Radio.Group
        value={marca.data.language}
        onChange={(e) => escolher(e.target.value)}
        disabled={gravar.isPending}
        options={IDIOMAS.map((i) => ({ value: i.value, label: i.label }))}
        style={{ display: "flex", flexDirection: "column", gap: 8 }}
      />
    </Space>
  );
}
