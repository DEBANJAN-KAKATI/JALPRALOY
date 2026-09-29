import { useI18n } from "../i18n";

export function Footer() {
  const { t } = useI18n();
  return (
    <footer className="footer">
      <p className="disclaimer">⚠ {t("disclaimer")}</p>
      <p>
        {t("sources")}: IMD · NASA GPM IMERG · NOAA GFS · ECMWF · Copernicus Sentinel-1 &amp; DEM · GloFAS · GDACS ·
        Open-Meteo · WorldPop · © OpenStreetMap contributors, CARTO
      </p>
      <p>
        ☎ {t("helplines")}: <a href="tel:112">112</a> · <a href="tel:1070">1070</a> · <a href="tel:1077">1077</a> · JalProloy — SIH
        PS 26071 (MoES / IMD)
      </p>
    </footer>
  );
}
