import { SPEECH_LANG, useI18n } from "../i18n";
import type { WarningColor } from "../lib/api";
import { COLOR_WORD_KEY } from "../lib/imd";

// Answer first: the banner is the first thing anyone reads.
export function AlertBanner({ color, text }: { color: WarningColor; text: string }) {
  const { t, lang } = useI18n();
  const word = t(COLOR_WORD_KEY[color]);

  function readAloud() {
    if (!("speechSynthesis" in window)) return;
    const u = new SpeechSynthesisUtterance(`${word}. ${text}`);
    u.lang = SPEECH_LANG[lang];
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  }

  return (
    <div className={`banner banner-${color}`} role="alert">
      <span className="badge">{word.toUpperCase()}</span>
      <span className="banner-text">{text}</span>
      <button className="link" onClick={readAloud} aria-label={t("read_aloud")}>🔊 {t("read_aloud")}</button>
    </div>
  );
}
