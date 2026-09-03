import os
import sys
import json
import csv
import io
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional

def load_entries(jsonl_path: str) -> List[Dict[str, Any]]:
    entries = []
    if not os.path.exists(jsonl_path):
        return entries
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            raw = line.strip()
            if not raw:
                continue
            try:
                entries.append(json.loads(raw))
            except Exception as e:
                print(f"WARN: line {i + 1} invalid JSON, skipping: {e}", file=sys.stderr)
    return entries

def to_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (str, int, float, bool)):
        return str(v)
    try:
        return json.dumps(v, separators=(',', ':'))
    except Exception:
        return str(v)

def data_text(e: Dict[str, Any]) -> str:
    d = e.get("data")
    if d is None:
        return ""
    if isinstance(d, dict):
        if "legacy_text" in d and isinstance(d["legacy_text"], str):
            return d["legacy_text"]
        parts = []
        for k, v in d.items():
            s = to_str(v)
            if len(s) > 60:
                s = s[:57] + "..."
            parts.append(f"{k}={s}")
        return " ".join(parts)
    return to_str(d)

def fmt_ts_short(ts: str) -> str:
    if not ts:
        return ""
    s = str(ts).replace("T", " ")
    if len(s) >= 16:
        return s[2:16]
    return s

def entry_date(e: Dict[str, Any]) -> Optional[datetime]:
    ts = to_str(e.get("ts"))
    if not ts:
        return None
    normalized = ts if ts.endswith("Z") else ts.replace("+00:00", "Z")
    normalized = normalized.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except Exception:
        return None

def matches_filters(e: Dict[str, Any], args: argparse.Namespace) -> bool:
    def contains_str(val: str, search: str) -> bool:
        if not val:
            return False
        return search.lower() in val.lower()

    if getattr(args, 'spec', None):
        top = to_str(e.get("spec_id"))
        d = e.get("data")
        blob = json.dumps(d) if isinstance(d, dict) else to_str(d)
        if not contains_str(top, args.spec) and not contains_str(blob, args.spec):
            return False

    if getattr(args, 'event', None):
        if not contains_str(to_str(e.get("event")), args.event):
            return False

    dt = entry_date(e)
    if getattr(args, 'after', None) and dt:
        try:
            a = datetime.fromisoformat(args.after + "T00:00:00+00:00")
            if dt < a:
                return False
        except Exception:
            pass

    if getattr(args, 'before', None) and dt:
        try:
            b = datetime.fromisoformat(args.before + "T23:59:59+00:00")
            if dt > b:
                return False
        except Exception:
            pass

    if getattr(args, 'grep', None):
        needle = args.grep.lower()
        blob = (json.dumps(e) + data_text(e)).lower()
        if needle not in blob:
            return False

    return True

def cmd_summary(entries: List[Dict[str, Any]], args: argparse.Namespace):
    lang = getattr(args, 'lang', 'pt') or 'pt'
    last_n = getattr(args, 'last', 20) or 20
    
    sorted_entries = sorted(entries, key=lambda x: to_str(x.get("ts")), reverse=True)[:last_n]
    
    if lang == "pt":
        print(f"📌 {len(sorted_entries)} decisões (mais novas primeiro, limit={last_n})")
    else:
        print(f"📌 {len(sorted_entries)} decisions (newest first, limit={last_n})")
        
    for e in sorted_entries:
        sid = f" ({to_str(e.get('spec_id'))})" if e.get("spec_id") else ""
        ev = to_str(e.get("event")).replace("_", " ") if lang == "pt" else to_str(e.get("event"))
        txt = data_text(e)[:120]
        print(f"- [{fmt_ts_short(to_str(e.get('ts')))}] {ev} | {txt}{sid}")

def cmd_filter(entries: List[Dict[str, Any]], args: argparse.Namespace):
    filtered = [e for e in entries if matches_filters(e, args)]
    sorted_entries = sorted(filtered, key=lambda x: to_str(x.get("ts")), reverse=True)
    
    last_n = getattr(args, 'last', None)
    if last_n:
        sorted_entries = sorted_entries[:last_n]
        
    print(f"Match: {len(sorted_entries)} entries")
    for e in sorted_entries:
        sid = f" [{to_str(e.get('spec_id'))}]" if e.get("spec_id") else ""
        ev = to_str(e.get("event")).replace("_", " ")
        txt = data_text(e)[:200]
        print(f"* [{to_str(e.get('ts'))}] {ev}{sid} — {txt}")

def cmd_export(entries: List[Dict[str, Any]], args: argparse.Namespace):
    fieldnames = ["ts", "event", "spec_id", "session_id", "worktree_root", "data_json"]
    delim = "," if args.format == "csv" else "\t"
    
    output = io.StringIO()
    writer = csv.writer(output, delimiter=delim, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(fieldnames)
    
    for e in entries:
        row = []
        for k in fieldnames:
            if k == "data_json":
                d = e.get("data", {})
                try:
                    row.append(json.dumps(d))
                except Exception:
                    row.append(to_str(d))
            else:
                row.append(to_str(e.get(k)))
        writer.writerow(row)
        
    out_str = output.getvalue()
    if getattr(args, 'out', None):
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out_str)
    else:
        sys.stdout.write(out_str)

def cmd_tail(entries: List[Dict[str, Any]], args: argparse.Namespace):
    last_n = getattr(args, 'last', 10) or 10
    slice_entries = entries[-last_n:]
    for e in slice_entries:
        sid = f" [{to_str(e.get('spec_id'))}]" if e.get("spec_id") else ""
        ev = to_str(e.get("event")).replace("_", " ")
        txt = data_text(e)[:200]
        print(f"[{to_str(e.get('ts'))}] {ev}{sid} — {txt}")

def main():
    parser = argparse.ArgumentParser(description="Decisions Query CLI")
    parser.add_argument("jsonl_path", help="Path to decisions.log.jsonl")
    
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    
    p_sum = subparsers.add_parser("summary")
    p_sum.add_argument("--last", type=int, default=20)
    p_sum.add_argument("--lang", choices=["pt", "en"], default="pt")
    
    p_fil = subparsers.add_parser("filter")
    p_fil.add_argument("--spec")
    p_fil.add_argument("--event")
    p_fil.add_argument("--after")
    p_fil.add_argument("--before")
    p_fil.add_argument("--grep")
    p_fil.add_argument("--last", type=int)
    
    p_exp = subparsers.add_parser("export")
    p_exp.add_argument("--format", choices=["csv", "tsv"], required=True)
    p_exp.add_argument("--out")
    
    p_tail = subparsers.add_parser("tail")
    p_tail.add_argument("--last", type=int, default=10)
    
    args = parser.parse_args()
    entries = load_entries(args.jsonl_path)
    
    if args.cmd == "summary":
        cmd_summary(entries, args)
    elif args.cmd == "filter":
        cmd_filter(entries, args)
    elif args.cmd == "export":
        cmd_export(entries, args)
    elif args.cmd == "tail":
        cmd_tail(entries, args)

if __name__ == "__main__":
    main()
