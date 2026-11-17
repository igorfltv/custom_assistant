#!/usr/bin/env python3
"""Score saved classification decisions without model calls or network access.

Usage: python scripts/evaluate-classification.py decision.json expected.json
Expected JSON: [{"item":1,"codes":["..."],"requires_information":false}, ...]
"""
import argparse
import json
from pathlib import Path

from forma_declaration_agent.classification_evaluation import evaluate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('decisions',type=Path)
    parser.add_argument('expected',type=Path)
    args=parser.parse_args()
    report=json.loads(args.decisions.read_text())
    # Accept a standalone saved classification or an evaluator's pipeline result.
    report=report.get('classification',report)
    print(json.dumps(evaluate(report,json.loads(args.expected.read_text())),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
