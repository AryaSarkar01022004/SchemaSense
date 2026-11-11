/**
 * Maps SchemaSense Chart Spec to Apache ECharts Options (Section 5.7).
 * Includes label truncation, containLabel grids, and chart-type overrides.
 */

function formatAxisLabel(raw: any, maxLen = 22): string {
  let s = String(raw ?? "");
  if (s.includes("|") && s.length > maxLen) {
    const parts = s.split("|").map((p) => p.trim()).filter(Boolean);
    if (parts.length > 0) {
      s = parts[parts.length - 1];
    }
  }
  return s.length > maxLen ? `${s.slice(0, maxLen - 1)}…` : s;
}

export function mapSpecToECharts(
  spec: any,
  rows: any[] = [],
  overrideType?: string,
  overrideYCol?: string
): any {
  if (!spec) return null;

  const chartType = overrideType || spec.type;
  const xCol = spec.x_axis;
  const yCol = overrideYCol || spec.y_axis;

  // If no override and prebuilt echarts_options exist, sanitize labels & grid so long strings never clip
  if (!overrideType && !overrideYCol && spec.echarts_options) {
    const opts = JSON.parse(JSON.stringify(spec.echarts_options));
    opts.grid = opts.grid || { left: 16, right: 20, top: 36, bottom: 24, containLabel: true };
    if (opts.xAxis && Array.isArray(opts.xAxis.data)) {
      const fullLabels = [...opts.xAxis.data];
      opts.xAxis.data = fullLabels.map((lbl: any) => formatAxisLabel(lbl, 24));
      opts.xAxis.axisLabel = {
        ...(opts.xAxis.axisLabel || {}),
        interval: fullLabels.length <= 15 ? 0 : "auto",
        rotate: fullLabels.length > 4 ? 25 : 0,
      };
      opts.tooltip = {
        ...(opts.tooltip || { trigger: "axis" }),
        formatter: (params: any) => {
          const items = Array.isArray(params) ? params : [params];
          if (!items.length) return "";
          const idx = items[0].dataIndex ?? 0;
          const fullTitle = String(fullLabels[idx] ?? items[0].name ?? "");
          const lines = items.map(
            (it: any) => `${it.marker || ""} ${it.seriesName || "Value"}: <b>${it.value}</b>`
          );
          return `<div style="max-width:320px;white-space:normal;"><b>${fullTitle.slice(0, 140)}</b><br/>${lines.join("<br/>")}</div>`;
        },
      };
    }
    return opts;
  }

  // Build options dynamically from rows (or from spec.echarts_options data if rows not loaded)
  const fallbackXData = spec.echarts_options?.xAxis?.data || [];
  const fallbackYData = spec.echarts_options?.series?.[0]?.data || [];

  const fullX = rows.length > 0 && xCol
    ? rows.map((r) => String(r[xCol] ?? ""))
    : fallbackXData.map((v: any) => String(v ?? ""));

  const yData = rows.length > 0 && yCol
    ? rows.map((r) => Number(r[yCol] ?? 0))
    : fallbackYData.map((v: any) => Number(v ?? 0));

  const shortX = fullX.slice(0, 25).map((v: string) => formatAxisLabel(v, 24));
  const slicedY = yData.slice(0, 25);

  if (chartType === "pie") {
    const pieData = fullX.slice(0, 12).map((lbl: string, i: number) => ({
      name: formatAxisLabel(lbl, 28),
      value: slicedY[i] ?? 0,
    }));
    return {
      tooltip: { trigger: "item", formatter: "{b}: <b>{c}</b> ({d}%)" },
      legend: { type: "scroll", bottom: 0 },
      series: [
        {
          name: yCol || "Value",
          type: "pie",
          radius: ["35%", "68%"],
          center: ["50%", "45%"],
          itemStyle: { borderRadius: 6, borderColor: "#fff", borderWidth: 2 },
          data: pieData,
        },
      ],
    };
  }

  if (chartType === "line") {
    return {
      tooltip: { trigger: "axis" },
      grid: { left: 16, right: 20, top: 36, bottom: 24, containLabel: true },
      xAxis: {
        type: "category",
        data: shortX,
        axisLabel: { rotate: shortX.length > 5 ? 25 : 0 },
      },
      yAxis: { type: "value" },
      series: [
        {
          name: yCol || "Value",
          type: "line",
          smooth: true,
          data: slicedY,
          itemStyle: { color: "#4f46e5" },
          areaStyle: {
            color: {
              type: "linear",
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(79, 70, 229, 0.25)" },
                { offset: 1, color: "rgba(79, 70, 229, 0.0)" },
              ],
            },
          },
        },
      ],
    };
  }

  if (chartType === "bar") {
    return {
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (params: any) => {
          const items = Array.isArray(params) ? params : [params];
          if (!items.length) return "";
          const idx = items[0].dataIndex ?? 0;
          const fullTitle = String(fullX[idx] ?? items[0].name ?? "");
          return `<div style="max-width:320px;white-space:normal;"><b>${fullTitle.slice(0, 140)}</b><br/>${yCol || "Value"}: <b>${items[0].value}</b></div>`;
        },
      },
      grid: { left: 16, right: 20, top: 36, bottom: 24, containLabel: true },
      xAxis: {
        type: "category",
        data: shortX,
        axisLabel: {
          interval: shortX.length <= 15 ? 0 : "auto",
          rotate: shortX.length > 4 ? 25 : 0,
        },
      },
      yAxis: { type: "value" },
      series: [
        {
          name: yCol || "Value",
          type: "bar",
          barMaxWidth: 48,
          data: slicedY,
          itemStyle: {
            color: "#4f46e5",
            borderRadius: [6, 6, 0, 0],
          },
        },
      ],
    };
  }

  if (chartType === "scatter") {
    const data = rows.map((r) => [Number(r[xCol] ?? 0), Number(r[yCol] ?? 0)]);
    return {
      tooltip: { trigger: "item" },
      grid: { left: 16, right: 20, top: 36, bottom: 24, containLabel: true },
      xAxis: { type: "value", name: xCol },
      yAxis: { type: "value", name: yCol },
      series: [
        {
          type: "scatter",
          symbolSize: 9,
          data,
          itemStyle: { color: "#4f46e5" },
        },
      ],
    };
  }

  return null;
}
