import { useState } from "react";
import dayjs from "dayjs";
import { DatePicker, Flex, Typography } from "antd";
import { Button as MButton, DatePicker as MDatePicker } from "antd-mobile";

import { useT } from "../../i18n/I18n";
import { useIsMobile } from "../../components/responsive";
import { diaProducao } from "./api";

/** Data de produção escolhida num calendário: grava sempre AAAA-MM-DD.
 *  Num lote antigo com texto que não é um dia certo ("2014", "Várias"),
 *  mostra esse texto por baixo e só o troca se se escolher uma data. */
export function DataProducaoCampo({ value, onChange }: { value?: string; onChange?: (v: string) => void }) {
  const t = useT();
  const mobile = useIsMobile();
  const [aberto, setAberto] = useState(false);
  const dia = diaProducao(value);
  const antigo = value?.trim() && !dia ? value.trim() : null;

  const aviso = antigo && (
    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
      {t("web.stock.prod_date_old", { valor: antigo })}
    </Typography.Text>
  );

  if (mobile)
    return (
      <Flex vertical gap={4}>
        <Flex gap={8} align="center">
          <MButton size="small" onClick={() => setAberto(true)}>
            {dia ? dayjs(dia).format("DD/MM/YYYY") : t("web.stock.prod_date_choose")}
          </MButton>
          {dia && (
            <MButton size="small" fill="none" onClick={() => onChange?.("")}>
              {t("web.stock.prod_date_clear")}
            </MButton>
          )}
        </Flex>
        {aviso}
        <MDatePicker
          visible={aberto}
          onClose={() => setAberto(false)}
          value={dia ? dayjs(dia).toDate() : new Date()}
          min={dayjs().subtract(40, "year").toDate()}
          max={new Date()}
          onConfirm={(v) => onChange?.(dayjs(v).format("YYYY-MM-DD"))}
        />
      </Flex>
    );

  return (
    <Flex vertical gap={4}>
      <DatePicker
        style={{ width: "100%" }}
        format="DD/MM/YYYY"
        placeholder={t("web.stock.prod_date_choose")}
        value={dia ? dayjs(dia) : null}
        disabledDate={(d) => d.isAfter(dayjs(), "day")}
        // Limpar num lote antigo apaga também o texto antigo.
        onChange={(d) => onChange?.(d ? d.format("YYYY-MM-DD") : "")}
      />
      {aviso}
    </Flex>
  );
}
