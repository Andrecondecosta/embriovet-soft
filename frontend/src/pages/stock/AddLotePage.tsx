import { useNavigate, useSearchParams } from "react-router-dom";
import { Button, Card, Col, Flex, Form, Input, InputNumber, Row } from "antd";
import { ArrowLeftOutlined } from "@ant-design/icons";

import { useT } from "../../i18n/I18n";
import { useIsMobile } from "../../components/responsive";
import { notifySuccess, useNotifyError } from "../../components/errors";
import { PageHeader } from "../../components/ds";
import { useCriarLote, type LoteNovo } from "./api";
import { CamposLote, DonoSelect, GaranhaoInput, Secao, camposVazios, useAjudaGaranhao } from "./LoteForm";

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
  const [form] = Form.useForm<LoteNovo>();
  const ajuda = useAjudaGaranhao(Form.useWatch("garanhao", form));

  const guardar = async (dados: LoteNovo) => {
    try {
      const lote = await criar.mutateAsync({ ...camposVazios(), ...dados });
      notifySuccess(t("web.stock.added"));
      // Como na app atual: volta aos Lotes, no garanhão do lote novo, com
      // o lote aberto.
      navigate(`/stock-semen/lotes?garanhao=${encodeURIComponent(lote.garanhao_nome)}&lote=${lote.id}`, { replace: true });
    } catch (err) {
      notifyError(err);
    }
  };

  return (
    <Card size="small" style={{ maxWidth: 1000 }}>
      <Button type="link" icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)} style={{ paddingInline: 0 }}>
        {t("web.stock.back")}
      </Button>
      <PageHeader titulo={t("web.stock.add")} />

      <Form
        form={form}
        layout="vertical"
        onFinish={guardar}
        onFinishFailed={() => window.scrollTo({ top: 0, behavior: "smooth" })}
        initialValues={{ ...camposVazios(), garanhao: params.get("garanhao") ?? "", palhetas: 0 }}
        scrollToFirstError
      >
        <Secao titulo={t("web.stock.add.identification")} primeiro>
          <Row gutter={12}>
            <Col xs={24} sm={12}>
              <Form.Item
                name="garanhao"
                label={t("label.garanhao")}
                extra={ajuda}
                rules={[{ required: true, whitespace: true, message: t("error.stallion_required") }]}
              >
                <GaranhaoInput />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12}>
              <Form.Item
                name="dono_id"
                label={t("add_stock.owner_semen").replace(" *", "")}
                rules={[{ required: true, message: t("web.stock.error.owner_required") }]}
              >
                <DonoSelect apenasAtivos={false} />
              </Form.Item>
            </Col>
          </Row>
        </Secao>

        <CamposLote
          producao={
            <Row gutter={12}>
              <Col xs={24} sm={8}>
                <Form.Item name="data_embriovet" label={t("stock.prod_date")}>
                  <Input />
                </Form.Item>
              </Col>
              <Col xs={24} sm={8}>
                <Form.Item
                  name="palhetas"
                  label={t("stock.straws_produced")}
                  rules={[{ required: true, type: "number", min: 1, message: t("error.straws_positive") }]}
                >
                  <InputNumber min={0} style={{ width: "100%" }} inputMode="numeric" />
                </Form.Item>
              </Col>
              <Col xs={24} sm={8}>
                <Form.Item name="origem_externa" label={t("stock.external_origin")}>
                  <Input />
                </Form.Item>
              </Col>
            </Row>
          }
        />

        {/* No telemóvel os botões ficam presos ao fundo do ecrã. */}
        <Flex
          gap={8}
          justify="flex-end"
          style={
            isMobile
              ? {
                  position: "sticky",
                  bottom: 0,
                  background: "#fff",
                  padding: "12px 0 calc(12px + env(safe-area-inset-bottom))",
                  borderTop: "1px solid #f0f0f0",
                  zIndex: 2,
                }
              : undefined
          }
        >
          <Button onClick={() => navigate(-1)} block={isMobile}>
            {t("web.common.cancel")}
          </Button>
          <Button type="primary" htmlType="submit" loading={criar.isPending} block={isMobile}>
            {t("btn.save")}
          </Button>
        </Flex>
      </Form>
    </Card>
  );
}
