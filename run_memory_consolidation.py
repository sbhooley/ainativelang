#!/usr/bin/env python3
"""
Execute AINL memory_consolidation.lang module.
Consolidates memory/*.md files into MEMORY.md with terse format.
"""

import sys
import os
import json
from datetime import datetime
from pathlib import Path
import re

WORKSPACE = Path("/data/.openclaw/workspace")
AINL_DIR = WORKSPACE / "ainativelang"
MEMORY_DIR = WORKSPACE / "memory"
MEMORY_FILE = WORKSPACE / "MEMORY.md"

sys.path.insert(0, str(AINL_DIR))

def extract_high_signal_lines(file_path, existing_lower):
    """
    Extract high-signal lines from a memory file.
    Keywords: important, fixed, config, todo, lesson, setting, changed, enabled, disabled, etc.
    """
    high_signal_keywords = [
        'important', 'fixed', 'config', 'preference', 'todo', 'lesson',
        'setting', 'requires', 'changed', 'created', 'enabled', 'disabled'
    ]
    
    items = []
    terse_prefixes = ['D: ', 'P: ', 'T: ', 'L: ', 'S: ']
    
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Warning: could not read {file_path}: {e}")
        return items
    
    for raw_line in lines:
        trimmed = raw_line.strip()
        
        # Skip empty or very short lines
        if len(trimmed) < 20:
            continue
        
        lower = trimmed.lower()
        
        # Check if already in MEMORY.md (dedup)
        if lower in existing_lower:
            continue
        
        # Check for high-signal keywords
        has_keyword = any(kw in lower for kw in high_signal_keywords)
        is_long = len(trimmed) >= 60
        
        # Check if already terse format
        is_terse = any(trimmed.startswith(p) for p in terse_prefixes)
        
        # Keep if terse format OR (has keyword AND long enough)
        if not (is_terse or (has_keyword and is_long)):
            continue
        
        # Stop if we hit cap
        if len(items) >= 50:
            break
        
        # If already terse, add as-is
        if is_terse:
            items.append(trimmed)
        else:
            # Auto-classify and prefix
            is_decision = any(x in lower for x in ['fixed', 'changed'])
            is_todo = any(x in lower for x in ['todo', 'requires'])
            is_lesson = any(x in lower for x in ['lesson', 'important'])
            is_setting = any(x in lower for x in ['setting', 'config', 'enabled', 'disabled', 'created'])
            
            # Priority: D > T > L > S > P
            if is_decision:
                prefix = "D: "
            elif is_todo:
                prefix = "T: "
            elif is_lesson:
                prefix = "L: "
            elif is_setting:
                prefix = "S: "
            else:
                prefix = "P: "
            
            # Truncate to 120 chars max
            if len(trimmed) > 120:
                trimmed = trimmed[:120]
            
            items.append(f"{prefix}{trimmed}")
    
    return items

def consolidate_memory():
    """Main consolidation logic."""
    
    now_iso = datetime.utcnow().isoformat() + "Z"
    
    # Check if memory dir exists
    if not MEMORY_DIR.exists():
        print("No memory directory found. Exiting.")
        return {"status": "no_memory_dir", "items_consolidated": 0, "files_processed": 0}
    
    # Read existing MEMORY.md
    existing_mem = ""
    existing_lower = []
    if MEMORY_FILE.exists():
        try:
            with open(MEMORY_FILE, 'r') as f:
                existing_mem = f.read()
                existing_lower = [line.strip().lower() for line in existing_mem.split('\n') if line.strip()]
        except Exception as e:
            print(f"Warning: could not read {MEMORY_FILE}: {e}")
    
    # List .md files in memory dir
    md_files = sorted([f.name for f in MEMORY_DIR.glob("*.md")])
    
    if not md_files:
        print("No memory files found.")
        return {"status": "no_files", "items_consolidated": 0, "files_processed": 0}
    
    # Process each file
    all_items = []
    for mfile in md_files:
        fpath = MEMORY_DIR / mfile
        items = extract_high_signal_lines(fpath, existing_lower)
        all_items.extend(items)
    
    # Deduplicate and take top items
    unique_items = []
    seen_lower = set(l.lower() for l in existing_lower)
    for item in all_items:
        if item.lower() not in seen_lower:
            unique_items.append(item)
            seen_lower.add(item.lower())
        if len(unique_items) >= 50:
            break
    
    if not unique_items:
        print("No new high-signal items found.")
        return {
            "status": "no_new_items",
            "items_consolidated": 0,
            "files_processed": len(md_files)
        }
    
    # Build consolidated section
    section_header = f"\n\n## Consolidated — {now_iso}\n"
    item_text = "\n".join(unique_items)
    section = section_header + item_text + "\n"
    
    # Append to MEMORY.md
    final_mem = existing_mem + section
    try:
        with open(MEMORY_FILE, 'w') as f:
            f.write(final_mem)
    except Exception as e:
        print(f"ERROR: could not write {MEMORY_FILE}: {e}")
        return {"status": "write_failed", "items_consolidated": 0, "files_processed": len(md_files)}
    
    return {
        "status": "success",
        "items_consolidated": len(unique_items),
        "files_processed": len(md_files),
        "section_header": section_header.strip(),
        "timestamp": now_iso,
        "message": f"Consolidated {len(unique_items)} terse items from {len(md_files)} memory files"
    }

if __name__ == "__main__":
    result = consolidate_memory()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "success" else 1)
