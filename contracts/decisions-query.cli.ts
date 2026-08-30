#!/usr/bin/env -S corepack pnpm exec tsx
/**
 * decisions-query.cli.ts — CLI helper for decisions.log.jsonl.
 * Part of harness-decisions-query global skill. Single writer = contracts helper;
 * this file = multi-mode READ-only tool for summaries / filters / exports / tail.
 *
 * Usage (equivalent à antiga versão Python):
 *   corepack pnpm --dir ~/.trae exec tsx ~/.trae/contracts/decisions-query.cli.ts <JSONL_PATH> summary [--last N] [--lang pt|en]
 *   corepack pnpm --dir ~/.trae exec tsx ~/.trae/contracts/decisions-query.cli.ts <JSONL_PATH> filter [--spec X] [--event X] [--after YYYY-MM-DD] [--before YYYY-MM-DD] [--grep X] [--last N]
 *   corepack pnpm --dir ~/.trae exec tsx ~/.trae/contracts/decisions-query.cli.ts <JSONL_PATH> export --format csv|tsv [--out FILE]
 *   corepack pnpm --dir ~/.trae exec tsx ~/.trae/contracts/decisions-query.cli.ts <JSONL_PATH> tail [--last N]
 *
 * Shortcut (via package.json scripts):
 *   corepack pnpm --dir ~/.trae decisions <JSONL_PATH> summary --lang pt
 */

import * as fs from "node:fs";
import * as path from "node:path";

type DecisionEntry = Record<string, unknown>;

function load(jsonlPath: string): DecisionEntry[] {
  const entries: DecisionEntry[] = [];
  const content = fs.readFileSync(jsonlPath, { encoding: "utf8" });
  const lines = content.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i]!.trim();
    if (!raw) continue;
    try {
      entries.push(JSON.parse(raw));
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      process.stderr.write(`WARN: line ${i + 1} invalid JSON, skipping: ${msg}\n`);
    }
  }
  return entries;
}

function toStr(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean" || typeof v === "bigint") return String(v);
  try {
    return JSON.stringify(v, undefined, 0);
  } catch {
    return String(v);
  }
}

function dataText(e: DecisionEntry): string {
  const d = e["data"];
  if (d === null || d === undefined) return "";
  if (typeof d === "object" && !Array.isArray(d)) {
    const rec = d as Record<string, unknown>;
    if ("legacy_text" in rec && typeof rec["legacy_text"] === "string") {
      return rec["legacy_text"];
    }
    const parts: string[] = [];
    for (const [k, v] of Object.entries(rec)) {
      let s: string;
      if (typeof v === "object" && v !== null) {
        try {
          s = JSON.stringify(v);
        } catch {
          s = String(v);
        }
      } else {
        s = String(v);
      }
      if (s.length > 60) s = s.slice(0, 57) + "...";
      parts.push(`${k}=${s}`);
    }
    return parts.join(" ");
  }
  return toStr(d);
}

function fmtTsShort(ts: string): string {
  if (!ts) return "";
  const s = ts.replace("T", " ");
  if (s.length >= 16) return s.slice(2, 16);
  return s;
}

interface FilterArgs {
  spec?: string;
  event?: string;
  after?: string;
  before?: string;
  grep?: string;
}

function parseDate(s: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return null;
  const d = new Date(`${s}T00:00:00Z`);
  return isNaN(d.getTime()) ? null : d;
}

function entryDate(e: DecisionEntry): Date | null {
  const ts = toStr(e["ts"]);
  if (!ts) return null;
  const normalized = ts.endsWith("Z") ? ts : ts.replace("+00:00", "Z");
  const d = new Date(normalized);
  return isNaN(d.getTime()) ? null : d;
}

function matchesFilters(e: DecisionEntry, args: FilterArgs): boolean {
  function containsSpec(val: string, spec: string): boolean {
    if (!val) return false;
    return val.toLowerCase() === spec.toLowerCase() || val.toLowerCase().includes(spec.toLowerCase());
  }
  function containsEvent(val: string, ev: string): boolean {
    if (!val) return false;
    return val.toLowerCase().includes(ev.toLowerCase());
  }

  if (args.spec) {
    const top = toStr(e["spec_id"]);
    const d = e["data"];
    const blob =
      d !== null && typeof d === "object"
        ? JSON.stringify(d)
        : toStr(d);
    if (!containsSpec(top, args.spec) && !containsSpec(blob, args.spec)) {
      return false;
    }
  }
  if (args.event) {
    const top = toStr(e["event"]);
    if (!containsEvent(top, args.event)) return false;
  }
  const dt = entryDate(e);
  if (args.after && dt) {
    const a = parseDate(args.after);
    if (a && dt < new Date(a.getFullYear(), a.getMonth(), a.getDate(), 0, 0, 0, 0)) return false;
  }
  if (args.before && dt) {
    const b = parseDate(args.before);
    if (b && dt > new Date(b.getFullYear(), b.getMonth(), b.getDate(), 23, 59, 59, 999)) return false;
  }
  if (args.grep) {
    const needle = args.grep.toLowerCase();
    const blob = (JSON.stringify(e) + dataText(e)).toLowerCase();
    if (!blob.includes(needle)) return false;
  }
  return true;
}

function takeLast<T>(arr: T[], n: number | undefined | null): T[] {
  if (n && n > 0) return arr.slice(-n);
  return arr;
}

function cmdSummary(entries: DecisionEntry[], args: { last?: number; lang?: "pt" | "en" }): void {
  const lang = args.lang ?? "pt";
  const lastN = args.last ?? 20;
  const sorted = [...entries].sort((a, b) => {
    const ta = toStr(a["ts"]);
    const tb = toStr(b["ts"]);
    return tb.localeCompare(ta);
  }).slice(0, lastN);
  if (lang === "pt") {
    process.stdout.write(`\u{1F4CC} ${sorted.length} decis\u00F5es (mais novas primeiro, limit=${lastN})\n`);
    for (const e of sorted) {
      const sid = e["spec_id"] ? ` (${toStr(e["spec_id"])})` : "";
      const ev = toStr(e["event"]).replace(/_/g, " ");
      const txt = dataText(e).slice(0, 120);
      process.stdout.write(`- [${fmtTsShort(toStr(e["ts"]))}] ${ev} | ${txt}${sid}\n`);
    }
  } else {
    process.stdout.write(`\u{1F4CC} ${sorted.length} decisions (newest first, limit=${lastN})\n`);
    for (const e of sorted) {
      const sid = e["spec_id"] ? ` (${toStr(e["spec_id"])})` : "";
      const ev = toStr(e["event"]);
      const txt = dataText(e).slice(0, 120);
      process.stdout.write(`- [${fmtTsShort(toStr(e["ts"]))}] ${ev} | ${txt}${sid}\n`);
    }
  }
}

function cmdFilter(entries: DecisionEntry[], args: FilterArgs & { last?: number }): void {
  const filtered = entries.filter((e) => matchesFilters(e, args));
  let sorted = [...filtered].sort((a, b) => {
    const ta = toStr(a["ts"]);
    const tb = toStr(b["ts"]);
    return tb.localeCompare(ta);
  });
  sorted = takeLast(sorted, args.last);
  process.stdout.write(`Match: ${sorted.length} entries\n`);
  for (const e of sorted) {
    const sid = e["spec_id"] ? ` [${toStr(e["spec_id"])}]` : "";
    const ev = toStr(e["event"]).replace(/_/g, " ");
    const txt = dataText(e).slice(0, 200);
    process.stdout.write(`* [${toStr(e["ts"])}] ${ev}${sid} \u2014 ${txt}\n`);
  }
}

interface ExportArgs {
  format: "csv" | "tsv";
  out?: string;
}

function csvEscape(s: string, delim: "," | "\t"): string {
  if (/[",\n\r\t]/.test(s) || (delim === "\t" && /\t/.test(s))) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

function cmdExport(entries: DecisionEntry[], args: ExportArgs): void {
  const fieldnames: Array<
    | "ts"
    | "event"
    | "spec_id"
    | "session_id"
    | "worktree_root"
    | "data_json"
  > = ["ts", "event", "spec_id", "session_id", "worktree_root", "data_json"];
  const delim: "," | "\t" = args.format === "csv" ? "," : "\t";
  const rows: string[] = [];
  rows.push(fieldnames.map((h) => csvEscape(h, delim)).join(delim));
  for (const e of entries) {
    const row = fieldnames.map((k) => {
      if (k === "data_json") {
        const d = e["data"] ?? {};
        try {
          return csvEscape(JSON.stringify(d), delim);
        } catch {
          return csvEscape(toStr(d), delim);
        }
      }
      return csvEscape(toStr(e[k]), delim);
    });
    rows.push(row.join(delim));
  }
  const out = rows.join("\n") + "\n";
  if (args.out) {
    fs.mkdirSync(path.dirname(path.resolve(args.out)), { recursive: true });
    fs.writeFileSync(args.out, out, { encoding: "utf8" });
  } else {
    process.stdout.write(out);
  }
}

function cmdTail(entries: DecisionEntry[], args: { last?: number }): void {
  const lastN = args.last ?? 10;
  const slice = entries.slice(-lastN);
  for (const e of slice) {
    const sid = e["spec_id"] ? ` [${toStr(e["spec_id"])}]` : "";
    const ev = toStr(e["event"]).replace(/_/g, " ");
    const txt = dataText(e).slice(0, 200);
    process.stdout.write(`[${toStr(e["ts"])}] ${ev}${sid} \u2014 ${txt}\n`);
  }
}

interface Parsed {
  path: string;
  cmd: "summary" | "filter" | "export" | "tail";
  summary: { last?: number; lang?: "pt" | "en" };
  filter: FilterArgs & { last?: number };
  export: ExportArgs;
  tail: { last?: number };
}

function parseCli(argv: string[]): Parsed {
  if (argv.length < 2) {
    process.stderr.write(
      "Usage: decisions-query.cli.ts <JSONL_PATH> <summary|filter|export|tail> [options]\n",
    );
    process.exit(2);
  }
  const p = argv[0]!;
  const cmd = argv[1] as Parsed["cmd"];
  const rest = argv.slice(2);
  const result: Parsed = {
    path: p,
    cmd,
    summary: {},
    filter: {},
    export: { format: "csv" },
    tail: {},
  };

  const opt = <T extends string | number | undefined>(name: string, coerce?: (v: string) => T): T | undefined => {
    const idx = rest.indexOf(`--${name}`);
    if (idx === -1) return undefined;
    const v = rest[idx + 1];
    if (v === undefined) return undefined;
    return coerce ? coerce(v) : (v as unknown as T);
  };

  if (cmd === "summary") {
    result.summary = {
      last: opt("last", (v) => parseInt(v, 10) || undefined),
      lang: opt("lang") as "pt" | "en" | undefined,
    };
  } else if (cmd === "filter") {
    result.filter = {
      spec: opt("spec"),
      event: opt("event"),
      after: opt("after"),
      before: opt("before"),
      grep: opt("grep"),
      last: opt("last", (v) => parseInt(v, 10) || undefined),
    };
  } else if (cmd === "export") {
    const fmt = opt("format");
    if (fmt !== "csv" && fmt !== "tsv") {
      process.stderr.write("export: --format csv|tsv required\n");
      process.exit(2);
    }
    result.export = { format: fmt, out: opt("out") };
  } else if (cmd === "tail") {
    result.tail = {
      last: opt("last", (v) => parseInt(v, 10) || undefined),
    };
  } else {
    process.stderr.write(`Unknown command: ${String(cmd)}\n`);
    process.exit(2);
  }

  return result;
}

function main(): void {
  const args = parseCli(process.argv.slice(2));
  const entries = load(args.path);
  if (args.cmd === "summary") cmdSummary(entries, args.summary);
  else if (args.cmd === "filter") cmdFilter(entries, args.filter);
  else if (args.cmd === "export") cmdExport(entries, args.export);
  else if (args.cmd === "tail") cmdTail(entries, args.tail);
}

main();
