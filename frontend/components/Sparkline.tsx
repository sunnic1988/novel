"use client";

import { motion } from "framer-motion";

export function Sparkline({
  data,
  color = "#22d3ee",
  height = 56,
  width = 200,
  yMin = 0,
  yMax = 1,
}: {
  data: Array<{ chapter: number; value: number }>;
  color?: string;
  height?: number;
  width?: number;
  yMin?: number;
  yMax?: number;
}) {
  if (!data || data.length === 0) {
    return (
      <div
        className="grid place-items-center text-[10px] text-slate-600"
        style={{ height, width }}
      >
        — 无数据 —
      </div>
    );
  }
  const minX = Math.min(...data.map((d) => d.chapter));
  const maxX = Math.max(...data.map((d) => d.chapter));
  const spanX = maxX - minX || 1;
  const spanY = yMax - yMin || 1;
  const pts = data.map((d) => {
    const x = ((d.chapter - minX) / spanX) * (width - 8) + 4;
    const y = height - ((d.value - yMin) / spanY) * (height - 8) - 4;
    return [x, y] as [number, number];
  });
  const path = pts
    .map(([x, y], i) => (i === 0 ? `M${x},${y}` : `L${x},${y}`))
    .join(" ");
  const area =
    `${path} L${pts[pts.length - 1][0]},${height} L${pts[0][0]},${height} Z`;
  return (
    <svg width={width} height={height} className="block">
      <defs>
        <linearGradient id={`grad-${color}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.45} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <motion.path
        d={area}
        fill={`url(#grad-${color})`}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      />
      <motion.path
        d={path}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 0.8 }}
      />
      {pts.map(([x, y], i) => (
        <circle
          key={i}
          cx={x}
          cy={y}
          r={1.5}
          fill={color}
          opacity={i === pts.length - 1 ? 1 : 0.5}
        />
      ))}
    </svg>
  );
}
