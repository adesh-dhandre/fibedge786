const fs = require("fs");

const file = "netlify_site/index.html";
const from = "const BASE='https://raw.githubusercontent.com/adesh-dhandre/fibedge786/master/';";
const to = "const BASE='/.netlify/functions/data?path=';";

const source = fs.readFileSync(file, "utf8");
if (!source.includes(from)) {
  throw new Error("FibEdge data base URL marker not found in netlify_site/index.html");
}

fs.writeFileSync(file, source.replace(from, to));
console.log("FibEdge dashboard data URLs rewritten to same-origin Netlify proxy.");
