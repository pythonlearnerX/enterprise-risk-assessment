// 图表公共配置 + 导出（SVG / PNG）
const CHART_TEXT = "#cbd5e1";
const CHART_GRID = "rgba(103,232,249,.12)";
const CHART_COLORS = ["#22d3ee", "#5eead4", "#60a5fa", "#c4b5fd", "#fca5a5", "#fde68a"];

const CHART_BASE = {
  color: CHART_COLORS,
  backgroundColor: "transparent",
  textStyle: {color: CHART_TEXT, fontFamily: "SimSun, serif"},
  animationDuration: 700,
  animationEasing: "cubicOut",
  tooltip: {
    backgroundColor: "rgba(8,16,28,.94)",
    borderColor: "rgba(103,232,249,.35)",
    textStyle: {color: "#e6edf7", fontSize: 12}
  },
  legend: {textStyle: {color: CHART_TEXT, fontSize: 12}, icon: "roundRect", itemWidth: 10, itemHeight: 10}
};

function axisStyle() {
  return {
    axisLine: {lineStyle: {color: CHART_GRID}},
    axisTick: {show: false},
    axisLabel: {color: "#93a8c4", fontSize: 11},
    splitLine: {lineStyle: {color: CHART_GRID, type: "dashed"}}
  };
}

function makeChart(el, option) {
  const chart = echarts.init(el, null, {renderer: "svg"});
  chart.setOption(Object.assign({}, CHART_BASE, option));
  window.addEventListener("resize", () => chart.resize());
  return chart;
}

function downloadSVG(chart, name) {
  const url = chart.getDataURL({type: "svg", pixelRatio: 1, backgroundColor: "#0b1220"});
  const a = document.createElement("a");
  a.href = url;
  a.download = name + ".svg";
  a.click();
}

function downloadPNG(chart, name, scale) {
  scale = scale || 2;
  const svgUrl = chart.getDataURL({type: "svg", pixelRatio: 1, backgroundColor: "#0b1220"});
  const img = new Image();
  img.onload = function () {
    const canvas = document.createElement("canvas");
    canvas.width = img.width * scale;
    canvas.height = img.height * scale;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#0b1220";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    const a = document.createElement("a");
    a.href = canvas.toDataURL("image/png");
    a.download = name + ".png";
    a.click();
  };
  img.src = svgUrl;
}

function bindExport(container, chart, name) {
  container.querySelectorAll("[data-export]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      if (btn.dataset.export === "svg") downloadSVG(chart, name);
      else downloadPNG(chart, name);
    });
  });
}