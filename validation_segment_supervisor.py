#!/usr/bin/env python3
"""Lightweight supervisor for persisted release-validation segments."""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
CHAIN = ROOT / "validation_segment_chain.py"

def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--count',type=int,required=True)
    parser.add_argument('--timeout',type=float,default=600.0)
    args=parser.parse_args()
    for index in range(args.count):
        completed=subprocess.run(
            [sys.executable,'-u',str(CHAIN),'--checkpoint',str(args.checkpoint)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=args.timeout,
            check=False,
        )
        print(completed.stdout,end='',flush=True)
        if completed.returncode != 0:
            print(f'SEGMENT SUPERVISOR FAILED index={index} exit={completed.returncode}',flush=True)
            return completed.returncode or 1
    return 0

if __name__=='__main__':
    raise SystemExit(main())
