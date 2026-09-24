const fs = require("fs");

const file = "netlify_site/index.html";
const from = "const BASE='https://raw.githubusercontent.com/adesh-dhandre/fibedge786/master/';";
const to = "const BASE='/.netlify/functions/data?path=';";

let source = fs.readFileSync(file, "utf8");
if (!source.includes(from)) {
  throw new Error("FibEdge data base URL marker not found in netlify_site/index.html");
}
source = source.replace(from, to);

const requestMarker = "async function requestScan(strategy,button){";
const refreshHelpers = `function scanDataVersion(strategy){
  if(strategy==='PREMIUMPLUS')return String(DATA.premiumPlus?.scan_finished_at_ist||DATA.premiumPlus?.updated_at||'');
  if(strategy==='STRATEGY05')return String(DATA.strategy05?.scan_finished_at_ist||DATA.strategy05?.updated_at||'');
  const rows=DATA.signals||[];
  let latest='';
  for(const r of rows){
    const t=String(r['Price Time']||'');
    if(t>latest)latest=t;
  }
  return latest||String(rows.length||'');
}
async function refreshAfterScan(strategy,beforeVersion){
  const deadline=Date.now()+30000;
  while(Date.now()<deadline){
    await loadAll(true);
    const afterVersion=scanDataVersion(strategy);
    if(afterVersion&&afterVersion!==beforeVersion)return true;
    setScanState(strategy,'Refreshing data…');
    await sleep(2000);
  }
  await loadAll(true);
  return false;
}
`;

if (!source.includes("function scanDataVersion(strategy){")) {
  if (!source.includes(requestMarker)) {
    throw new Error("FibEdge requestScan marker not found in netlify_site/index.html");
  }
  source = source.replace(requestMarker, refreshHelpers + "\n" + requestMarker);
}

const startMarker = "  const startedMs=Date.now();\n  let timer=null;";
const startReplacement = "  const startedMs=Date.now();\n  const beforeDataVersion=scanDataVersion(strategy);\n  let timer=null;";
if (!source.includes(startMarker)) {
  throw new Error("FibEdge scan start marker not found in netlify_site/index.html");
}
source = source.replace(startMarker, startReplacement);

const refreshMarker = "      await sleep(2500);\n      await loadAll(true);";
const refreshReplacement = "      const dataRefreshed=await refreshAfterScan(strategy,beforeDataVersion);\n      setScanState(strategy,'Completed ✓');\n      setScanDuration(strategy,result.duration_seconds??((Date.now()-startedMs)/1000));\n      if(!dataRefreshed)console.warn('FibEdge scan completed, but refreshed data was not visible within 30 seconds.');";
if (!source.includes(refreshMarker)) {
  throw new Error("FibEdge post-scan refresh marker not found in netlify_site/index.html");
}
source = source.replace(refreshMarker, refreshReplacement);

fs.writeFileSync(file, source);
console.log("FibEdge dashboard data URLs rewritten to same-origin Netlify proxy.");
console.log("FibEdge post-scan auto-refresh retry enabled.");
