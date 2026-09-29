import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from "react";
import { useI18n } from "../i18n";

export interface Slide {
  key: string;
  icon: string;
  title: string;
  content: ReactNode;
}

const STORE_KEY = "slide";

/** One topic at a time instead of a wall of cards: pill tabs, ←/→ arrows, dots,
 * keyboard arrows and touch swipe. Only the active slide is rendered. */
export function SlideDeck({ slides }: { slides: Slide[] }) {
  const { t } = useI18n();
  const [index, setIndex] = useState(() => {
    try {
      const i = slides.findIndex((s) => s.key === localStorage.getItem(STORE_KEY));
      return i >= 0 ? i : 0;
    } catch {
      return 0;
    }
  });
  const [dir, setDir] = useState<1 | -1>(1);
  const startX = useRef<number | null>(null);
  const tabsRef = useRef<HTMLDivElement>(null);

  function go(i: number) {
    const next = (i + slides.length) % slides.length;
    setDir(next >= index ? 1 : -1);
    setIndex(next);
    try {
      localStorage.setItem(STORE_KEY, slides[next].key);
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    // Centre the active pill by scrolling the pill strip only — scrollIntoView would
    // also scroll the whole page down to the deck on first load.
    const strip = tabsRef.current;
    const pill = strip?.querySelector<HTMLElement>(".active");
    if (strip && pill) strip.scrollTo({ left: pill.offsetLeft - (strip.clientWidth - pill.clientWidth) / 2, behavior: "smooth" });
  }, [index]);

  function onKey(e: KeyboardEvent<HTMLDivElement>) {
    if ((e.target as HTMLElement).closest("input, select, textarea")) return;
    if (e.key === "ArrowRight") go(index + 1);
    if (e.key === "ArrowLeft") go(index - 1);
  }
  const onDown = (e: PointerEvent) => {
    if (e.pointerType !== "mouse") startX.current = e.clientX;
  };
  const onUp = (e: PointerEvent) => {
    if (startX.current == null) return;
    const dx = e.clientX - startX.current;
    startX.current = null;
    if (Math.abs(dx) > 60) go(index + (dx < 0 ? 1 : -1));
  };

  const slide = slides[index];
  return (
    <section className="deck" aria-roledescription="carousel" tabIndex={0} onKeyDown={onKey}>
      <div className="deck-bar">
        <button className="deck-arrow" onClick={() => go(index - 1)} aria-label={t("prev")}>‹</button>
        <div className="deck-tabs" role="tablist" ref={tabsRef}>
          {slides.map((s, i) => (
            <button key={s.key} role="tab" aria-selected={i === index} className={i === index ? "active" : ""} onClick={() => go(i)}>
              <span aria-hidden="true">{s.icon}</span> {s.title}
            </button>
          ))}
        </div>
        <button className="deck-arrow" onClick={() => go(index + 1)} aria-label={t("next")}>›</button>
      </div>
      <div
        key={slide.key}
        className={`deck-slide ${dir > 0 ? "from-right" : "from-left"}`}
        role="tabpanel"
        aria-label={`${slide.title} (${index + 1} / ${slides.length})`}
        onPointerDown={onDown}
        onPointerUp={onUp}
      >
        {slide.content}
      </div>
      <div className="deck-dots" aria-hidden="true">
        {slides.map((s, i) => (
          <button key={s.key} className={i === index ? "on" : ""} onClick={() => go(i)} tabIndex={-1} />
        ))}
        <span className="deck-count">{index + 1} / {slides.length}</span>
      </div>
    </section>
  );
}
