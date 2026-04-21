/**
 * flows_cronusfarm_dashboard.json 에 펌프 주기 ui_dropdown(분/초) 옵션을 주입합니다.
 * (수동 편집 시 BOM/따옴표 실수 방지)
 */
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
const flowPath = path.join(root, "nodered", "flows_cronusfarm_dashboard.json");
const optPath = path.join(__dirname, "dd_options.json");

function stripBom(s) {
  return s.charCodeAt(0) === 0xfeff ? s.slice(1) : s;
}

let rawOpt = fs.readFileSync(optPath, "utf8");
const opts = JSON.parse(stripBom(rawOpt));
const minOpt = opts.min;
const secOpt = opts.sec;

const flow = JSON.parse(stripBom(fs.readFileSync(flowPath, "utf8")));

const ddIds = [
  "dd_on_pump_a1_m",
  "dd_on_pump_a1_s",
  "dd_off_pump_a1_m",
  "dd_off_pump_a1_s",
  "dd_on_pump_a2_m",
  "dd_on_pump_a2_s",
  "dd_off_pump_a2_m",
  "dd_off_pump_a2_s",
  "dd_on_pump_b1_m",
  "dd_on_pump_b1_s",
  "dd_off_pump_b1_m",
  "dd_off_pump_b1_s",
  "dd_on_pump_b2_m",
  "dd_on_pump_b2_s",
  "dd_off_pump_b2_m",
  "dd_off_pump_b2_s",
];

for (const id of ddIds) {
  const n = flow.find((x) => x.id === id);
  if (!n) {
    console.error("missing node", id);
    process.exit(1);
  }
  const useMin = id.endsWith("_m");
  n.options = useMin ? minOpt : secOpt;
}

fs.writeFileSync(flowPath, JSON.stringify(flow, null, 2) + "\n", "utf8");
console.log("patched options for", ddIds.length, "dropdowns");
