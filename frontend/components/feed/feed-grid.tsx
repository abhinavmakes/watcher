"use client";

import { AnimatePresence, MotionConfig, motion } from "motion/react";

import type { ClusterCard as ClusterCardModel } from "@/lib/types";

import { ClusterCard } from "./cluster-card";

const FEATURE_COUNT = 2;
const MIN_FOR_FEATURES = 4;

const cardTransition = (index: number) => ({
  duration: 0.25,
  delay: Math.min(index * 0.03, 0.3),
});

function CardCell({
  card,
  index,
  variant,
}: {
  card: ClusterCardModel;
  index: number;
  variant: "feature" | "standard";
}) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 16, scale: 0.97 }}
      whileInView={{ opacity: 1, y: 0, scale: 1, transition: cardTransition(index) }}
      viewport={{ once: true, margin: "-80px" }}
      exit={{ opacity: 0, scale: 0.96, transition: { duration: 0.2 } }}
      whileHover={{ y: -4 }}
      transition={{ duration: 0.2 }}
    >
      <ClusterCard card={card} variant={variant} />
    </motion.div>
  );
}

export function FeedGrid({ cards }: { cards: ClusterCardModel[] }) {
  const sorted = [...cards].sort((a, b) => b.momentum - a.momentum);
  const useFeatures = sorted.length >= MIN_FOR_FEATURES;
  const features = useFeatures ? sorted.slice(0, FEATURE_COUNT) : [];
  const standard = useFeatures ? sorted.slice(FEATURE_COUNT) : sorted;

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex flex-col gap-4">
        {features.length > 0 && (
        <motion.div layout className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <AnimatePresence mode="popLayout">
            {features.map((card, index) => (
              <CardCell key={card.id} card={card} index={index} variant="feature" />
            ))}
          </AnimatePresence>
        </motion.div>
      )}

      {standard.length > 0 && (
        <motion.div
          layout
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
        >
          <AnimatePresence mode="popLayout">
            {standard.map((card, index) => (
              <CardCell key={card.id} card={card} index={index} variant="standard" />
            ))}
          </AnimatePresence>
        </motion.div>
      )}
      </div>
    </MotionConfig>
  );
}
