const fs = require("fs");
const path = require("path");

function getParser() {
  const localPath = path.join(__dirname, "node_modules", "fifa-career-save-parser");
  if (fs.existsSync(localPath)) {
    return require(localPath);
  }
  return require("fifa-career-save-parser");
}

function scoreDb(db) {
  const tables = Object.keys(db || {});
  let rows = 0;
  for (const t of tables) {
    const value = db[t];
    if (Array.isArray(value)) {
      rows += value.length;
    }
  }
  return tables.length * 1000000 + rows;
}

async function parseWithBestVersion(parser, inputBuffer) {
  const versions = ["21", "20", "19", "18", "17"];
  let best = null;
  let bestScore = -1;
  for (const version of versions) {
    try {
      const out = await parser(inputBuffer, version);
      const dbs = Array.isArray(out) ? out : [out];
      const db0 = dbs[0] || {};
      const db1 = dbs[1] || {};
      const score = scoreDb(db0) + scoreDb(db1);
      if (score > bestScore) {
        bestScore = score;
        best = { version, db0, db1 };
      }
    } catch (err) {
    }
  }
  return best;
}

async function main() {
  const inputPath = process.argv[2];
  const outputPath = process.argv[3];
  if (!inputPath || !outputPath) {
    throw new Error("Usage: node parse_fbchunks.js <input-save> <output-json>");
  }
  const parser = getParser();
  const inputBuffer = fs.readFileSync(inputPath);
  const best = await parseWithBestVersion(parser, inputBuffer);
  if (!best) {
    throw new Error("Unable to parse save with supported schemas");
  }
  const payload = {
    ok: true,
    version: best.version,
    db0: best.db0 || {},
    db1: best.db1 || {},
  };
  fs.writeFileSync(outputPath, JSON.stringify(payload), "utf8");
  process.stdout.write(`ok version=${best.version}\n`);
}

main().catch((err) => {
  process.stderr.write(String((err && err.stack) || err));
  process.exit(1);
});
