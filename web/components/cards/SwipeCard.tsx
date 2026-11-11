"use client";
import { motion, useMotionValue, useTransform, useReducedMotion, animate } from "framer-motion";
import type { ReactNode } from "react";

export type SwipeAction = "noted" | "less";
const THRESHOLD = 96; // px of drag before a release commits

/** Horizontal swipe: right = noted (keep showing this kind), left = less (show fewer). Click-through is preserved. */
export default function SwipeCard({ children, onSwipe }: { children: ReactNode; onSwipe: (a: SwipeAction) => void }) {
  const x = useMotionValue(0);
  const reduce = useReducedMotion();
  const notedOpacity = useTransform(x, [20, THRESHOLD], [0, 1]);
  const lessOpacity = useTransform(x, [-THRESHOLD, -20], [1, 0]);
  const rotate = useTransform(x, [-240, 240], [-4, 4]);

  return (
    <div className="relative">
      <div className="pointer-events-none absolute inset-0 flex items-center justify-between rounded-xl px-4 text-[12px] font-medium uppercase tracking-wide">
        <motion.span style={{ opacity: notedOpacity }} className="rounded-full bg-up/15 px-2 py-1 text-up">Noted</motion.span>
        <motion.span style={{ opacity: lessOpacity }} className="rounded-full bg-down/15 px-2 py-1 text-down">Less of this</motion.span>
      </div>
      <motion.div
        drag="x"
        dragElastic={0.6}
        dragConstraints={{ left: 0, right: 0 }}
        dragSnapToOrigin
        style={{ x, rotate: reduce ? 0 : rotate }}
        onDragEnd={(_, info) => {
          const dx = info.offset.x;
          if (Math.abs(dx) < THRESHOLD) return;
          const action: SwipeAction = dx > 0 ? "noted" : "less";
          const to = dx > 0 ? 480 : -480;
          animate(x, to, { duration: reduce ? 0 : 0.22, ease: "easeIn" }).then(() => onSwipe(action));
        }}
        whileTap={{ cursor: "grabbing" }}
        className="touch-pan-y"
      >
        {children}
      </motion.div>
    </div>
  );
}
