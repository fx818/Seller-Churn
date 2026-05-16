#!/usr/bin/env python3
"""
Root-level convenience wrapper for the churn_analysis skill runner.

Usage:
  python run_skill.py --list
  python run_skill.py <skill_name> <GLID>
  python run_skill.py <skill_name> <GLID> --pretty
  python run_skill.py pipeline --glid <GLID>
  python run_skill.py pipeline --glids-file glids.txt --no-llm
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from churn_analysis.cli import main as _main

# Remap --list → skills subcommand
if len(sys.argv) > 1 and sys.argv[1] in ("--list", "list"):
    sys.argv[1] = "skills"

_main()
