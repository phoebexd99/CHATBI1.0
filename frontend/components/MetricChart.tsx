"use client";

import * as echarts from "echarts";
import { useEffect, useRef } from "react";

export default function MetricChart({ columns, rows, type }: { columns: string[]; rows: unknown[][]; type: string }) {
  const element = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!element.current) return;
    const chart = echarts.init(element.current);
    const scalar = columns.length === 1;
    chart.setOption(scalar ? {
      graphic: [{ type: "text", left: "center", top: "middle", style: { text: `¥${Number(rows[0]?.[0] ?? 0).toLocaleString("zh-CN", { minimumFractionDigits: 2 })}`, fill: "#1f6b46", font: "600 38px Georgia" } }]
    } : {
      grid: { left: 42, right: 12, top: 16, bottom: 32 },
      xAxis: { type: "category", data: rows.map(row => String(row[0])), axisLine: { lineStyle: { color: "#cbd5cc" } } },
      yAxis: { type: "value", splitLine: { lineStyle: { color: "#e8ece8" } } },
      series: [{ type: type === "line" ? "line" : "bar", data: rows.map(row => Number(row[row.length - 1])), itemStyle: { color: "#1f6b46", borderRadius: [4, 4, 0, 0] }, smooth: true }]
    });
    const resize = () => chart.resize(); window.addEventListener("resize", resize);
    return () => { window.removeEventListener("resize", resize); chart.dispose(); };
  }, [columns, rows, type]);
  return <div className="chart" ref={element} />;
}

