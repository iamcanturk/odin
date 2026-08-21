"use client";

import { useState } from "react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import { Modal } from "@/components/Modal";
import { Composer, type ComposerSeed } from "@/components/Composer";
import { ScoreMeter } from "@/components/ui";

/**
 * What the feed hands the modal. Deliberately flat: events, raw items, pulse tweets
 * and your own posts are different shapes, and the modal shouldn't have to know which
 * of them it's showing.
 */
export interface FeedItem {
  id: string;
  title: string;
  body?: string | null;
  image?: string | null;
  url?: string | null;
  sourceLabel?: string | null;
  category?: string | null;
  chips?: string[];
  /** Other headlines merged into this event — invisible everywhere else. */
  extras?: string[];
  meta?: string | null;
  scores?: { label: string; value: number }[];
  eventId?: string | null;
  /** What the composer should start from; falls back to body, then title. */
  seedText?: string;
}

/**
 * Two states in one surface.
 *
 * `preview` gives the item the whole width — image, full summary, merged headlines —
 * which is what the pinned side column couldn't afford to do. "Bunu seç" then swaps
 * to `compose` without closing, so the source stays on screen beside the draft
 * instead of being replaced by it.
 */
export function FeedItemModal({
  item,
  onClose,
}: {
  item: FeedItem | null;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const [composing, setComposing] = useState(false);

  const close = () => {
    setComposing(false);
    onClose();
  };

  if (!item) return null;

  const seed: ComposerSeed = {
    topic: item.seedText || item.body || item.title,
    eventId: item.eventId ?? undefined,
    source: item.sourceLabel ?? undefined,
  };

  return (
    <Modal open onClose={close} wide={composing}>
      <div className={composing ? "grid gap-0 md:grid-cols-[minmax(0,1fr)_400px]" : ""}>
        {/* Source pane. Condensed once you're writing — still readable, out of the way. */}
        <div className={composing ? "p-5 border-b md:border-b-0 md:border-r border-border" : "p-6"}>
          {item.image && !composing && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={item.image}
              alt=""
              className="w-full max-h-72 object-cover rounded-lg mb-4"
            />
          )}

          <div className="flex flex-wrap items-center gap-2 pr-8">
            {item.sourceLabel && (
              <span className="text-[10px] font-mono uppercase tracking-widest text-accent">
                {item.sourceLabel}
              </span>
            )}
            {item.category && (
              <span className="rounded border border-border px-1.5 py-0.5 text-[10px] uppercase text-faint">
                {item.category}
              </span>
            )}
            {item.chips?.map((c) => (
              <span
                key={c}
                className="rounded-full border border-good/40 px-2 py-0.5 text-[10px] text-good"
              >
                {c}
              </span>
            ))}
            {item.meta && <span className="text-[11px] text-faint">{item.meta}</span>}
          </div>

          <h2
            className={`font-medium text-text mt-2 ${composing ? "text-base" : "text-xl leading-snug"}`}
          >
            {item.title}
          </h2>

          {item.body && (
            <p
              className={`text-sm text-muted mt-3 whitespace-pre-wrap leading-relaxed ${
                composing ? "line-clamp-6" : ""
              }`}
            >
              {item.body}
            </p>
          )}

          {!composing && !!item.extras?.length && (
            <ul className="mt-4 flex flex-col gap-1.5">
              {item.extras.map((h) => (
                <li key={h} className="text-[13px] text-faint">
                  ↳ {h}
                </li>
              ))}
            </ul>
          )}

          {!composing && !!item.scores?.length && (
            <div className="flex flex-wrap gap-x-8 gap-y-3 mt-5">
              {item.scores.map((s) => (
                <ScoreMeter key={s.label} label={s.label} score={s.value} />
              ))}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3 mt-5">
            {!composing && (
              <button
                onClick={() => setComposing(true)}
                className="rounded-lg border border-accent/60 bg-accent/10 px-4 py-2 text-sm text-accent hover:bg-accent/20 transition-colors"
              >
                {t("fm.select")} →
              </button>
            )}
            {item.url && (
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[11px] text-muted hover:text-accent transition-colors"
              >
                {t("fm.open")} ↗
              </a>
            )}
            {item.eventId && (
              <Link
                href={`/events/${item.eventId}`}
                className="text-[11px] text-muted hover:text-accent transition-colors"
              >
                {t("ev.detail")} →
              </Link>
            )}
          </div>
        </div>

        {composing && (
          <div className="p-4">
            <Composer seed={seed} />
          </div>
        )}
      </div>
    </Modal>
  );
}
