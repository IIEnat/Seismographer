#!/usr/bin/env python3
"""
make_readme.py — generate concise Markdown for the Seismic Drilldown tool.

Usage:
  python make_readme.py                   # prints to stdout
  python make_readme.py -o README.md      # writes to README.md
  python make_readme.py -t "My Title" -u "http://127.0.0.1:8000" -l 3000
"""
from __future__ import annotations
import argparse
from textwrap import dedent

def build_markdown(title: str, url: str, lod_default: int) -> str:
    return dedent(f"""\
    ## {title}

    Browser-based viewer for seismic MiniSEED data.

    ```bash
    python serve_data.py
    ```

    Open [{url}]({url}) in your browser.

    **Options:**  
    - **Station** – select station folder.  
    - **File/Hour** – choose MiniSEED file (by timestamp).  
    - **Channel** – pick channel (HNX, HNY, HNZ).  
    - **LOD max points** – control downsampling (default {lod_default}, higher = smoother zoom).  
    - **Load** – fetch and plot data.  

    **Features:**  
    Zoom & pan on waveform, min/max envelope sampling for large files, and toolbar tools (reset, zoom, save, inspect).
    """)

def main():
    p = argparse.ArgumentParser(description="Generate Markdown overview.")
    p.add_argument("-t", "--title", default="Seismic Drilldown Tool")
    p.add_argument("-u", "--url", default="http://127.0.0.1:8000")
    p.add_argument("-l", "--lod-default", type=int, default=3000)
    p.add_argument("-o", "--output", help="Write to file instead of stdout")
    args = p.parse_args()

    md = build_markdown(args.title, args.url, args.lod_default)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"Wrote {args.output}")
    else:
        print(md)

if __name__ == "__main__":
    main()
