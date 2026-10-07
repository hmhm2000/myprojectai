// Checks the translations:
//  1. every static key used in code - t("a.b") / <Trans k="a.b"> - exists in every locale,
//  2. no Polish characters outside src/i18n/locales (user-facing text must live in locale files).
// Run: npm run check:i18n
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const SRC = join(dirname(fileURLToPath(import.meta.url)), "..", "src");
const LOCALES_DIR = join(SRC, "i18n", "locales");

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
}

function hasKey(messages, key) {
  const value = key.split(".").reduce((node, part) => (node == null ? undefined : node[part]), messages);
  return typeof value === "string" || (value != null && typeof value === "object" && "other" in value);
}

const locales = {};
for (const language of readdirSync(LOCALES_DIR)) {
  locales[language] = (await import(pathToFileURL(join(LOCALES_DIR, language, "index.js")).href)).default;
}

const KEY_PATTERNS = [/\bt\(\s*"([\w.]+)"/g, /\bk="([\w.]+)"/g, /hasTranslation\(\s*"([\w.]+)"/g];
const POLISH = /[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ„”]/;

const problems = [];
const codeFiles = walk(SRC).filter((f) => /\.(jsx?|css)$/.test(f) && !f.startsWith(LOCALES_DIR));

for (const file of codeFiles) {
  const text = readFileSync(file, "utf8");
  const name = relative(SRC, file);
  for (const pattern of KEY_PATTERNS) {
    for (const [, key] of text.matchAll(pattern)) {
      for (const [language, messages] of Object.entries(locales)) {
        if (!hasKey(messages, key)) problems.push(`${name}: missing key "${key}" in locale "${language}"`);
      }
    }
  }
  text.split("\n").forEach((line, index) => {
    if (POLISH.test(line)) problems.push(`${name}:${index + 1}: Polish text outside locale files: ${line.trim()}`);
  });
}

if (problems.length) {
  console.error(problems.join("\n"));
  console.error(`\n✗ ${problems.length} problem(s)`);
  process.exit(1);
}
console.log(`✓ i18n OK (${codeFiles.length} files, locales: ${Object.keys(locales).join(", ")})`);
