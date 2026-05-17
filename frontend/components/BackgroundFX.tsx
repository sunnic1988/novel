"use client";

import { motion } from "framer-motion";

export function BackgroundFX() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div
        className="absolute inset-0 opacity-[0.18]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(56,189,248,0.18) 1px, transparent 1px), linear-gradient(90deg, rgba(56,189,248,0.18) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          maskImage:
            "radial-gradient(circle at 50% 0%, black 0%, transparent 70%)",
          WebkitMaskImage:
            "radial-gradient(circle at 50% 0%, black 0%, transparent 70%)",
        }}
      />
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className="absolute rounded-full blur-3xl"
          style={{
            width: 380,
            height: 380,
            background:
              i === 0
                ? "radial-gradient(circle, rgba(34,211,238,0.35), transparent 70%)"
                : i === 1
                ? "radial-gradient(circle, rgba(99,102,241,0.30), transparent 70%)"
                : "radial-gradient(circle, rgba(59,130,246,0.30), transparent 70%)",
            top: i === 0 ? -120 : i === 1 ? "30%" : "70%",
            left: i === 0 ? "10%" : i === 1 ? "75%" : "30%",
          }}
          animate={{
            x: [0, 30, -20, 0],
            y: [0, 20, -10, 0],
          }}
          transition={{ duration: 14 + i * 3, repeat: Infinity, ease: "easeInOut" }}
        />
      ))}
    </div>
  );
}
