// Uploads knowledge_base/*.md to Vercel Blob storage and records the resulting
// public URLs in knowledge_base/blob_manifest.json, so rag.py fetches the live
// Blob copy at runtime instead of the file bundled at deploy time.
//
// Usage: npm run ingest
//
// Requires BLOB_READ_WRITE_TOKEN in config.env (Vercel dashboard -> Storage ->
// your Blob store -> Quickstart / .env.local tab).

import { spawnSync } from "node:child_process";
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const KB_DIR = path.join(ROOT, "knowledge_base");
const MANIFEST_PATH = path.join(KB_DIR, "blob_manifest.json");

function loadConfigEnv() {
  const configPath = path.join(ROOT, "config.env");
  const lines = readFileSync(configPath, "utf-8").split("\n");
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    const value = trimmed.slice(eq + 1).trim();
    if (!(key in process.env)) process.env[key] = value;
  }
}

function extractBlobUrl(output) {
  const match = output.match(/https?:\/\/\S+blob\.vercel-storage\.com\S*/);
  return match ? match[0] : null;
}

function main() {
  loadConfigEnv();

  const token = process.env.BLOB_READ_WRITE_TOKEN;
  if (!token || token === "your_blob_read_write_token_here") {
    console.error(
      "BLOB_READ_WRITE_TOKEN is not set. Add it to config.env - see the comment above " +
        "that line for where to find it in the Vercel dashboard."
    );
    process.exit(1);
  }

  const manifest = (() => {
    try {
      return JSON.parse(readFileSync(MANIFEST_PATH, "utf-8"));
    } catch {
      return {};
    }
  })();

  const files = readdirSync(KB_DIR).filter((f) => f.endsWith(".md"));
  if (files.length === 0) {
    console.error(`No .md files found in ${KB_DIR}`);
    process.exit(1);
  }

  for (const file of files) {
    const filePath = path.join(KB_DIR, file);
    console.log(`Uploading ${file}...`);

    // Vercel CLI prints "Success! <url>" to stderr, not stdout, so both streams
    // must be captured and searched together.
    const result = spawnSync(
      "npx",
      ["vercel", "blob", "put", filePath, "--access", "private", "--allow-overwrite", "--rw-token", token],
      { encoding: "utf-8", shell: true }
    );
    const output = `${result.stdout ?? ""}${result.stderr ?? ""}`;

    const url = extractBlobUrl(output);
    if (!url) {
      console.error(`  Upload did not return a blob URL for ${file}. Raw output:\n${output}`);
      continue;
    }

    manifest[file] = url;
    console.log(`  -> ${url}`);
  }

  writeFileSync(MANIFEST_PATH, JSON.stringify(manifest, null, 2) + "\n");
  console.log(`\nUpdated ${path.relative(ROOT, MANIFEST_PATH)}`);
}

main();
