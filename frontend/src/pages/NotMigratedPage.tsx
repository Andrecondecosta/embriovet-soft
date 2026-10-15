import { useLocation } from "react-router-dom";
import { Card, Result } from "antd";
import { ClockCircleOutlined } from "@ant-design/icons";

import { useT } from "../i18n/I18n";
import { NAV } from "../components/Shell";

/** Lugar das páginas que ainda só existem na app Streamlit. */
export function NotMigratedPage() {
  const t = useT();
  const { pathname } = useLocation();
  const item = NAV.find((n) => n.path === pathname);
  return (
    <Card>
      <Result
        icon={<ClockCircleOutlined style={{ color: "#bfbfbf" }} />}
        title={item ? t(item.label) : t("web.not_migrated.title")}
        subTitle={
          <>
            <b>{t("web.not_migrated.title")}</b>
            <br />
            {t("web.not_migrated.text")}
          </>
        }
      />
    </Card>
  );
}
