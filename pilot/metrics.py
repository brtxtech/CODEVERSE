"""Local, pseudonymous pilot evaluation; no CV contents, names, email or tokens.

Usage: python -m pilot.metrics pilot/journeys.csv --output pilot/report.json
"""
import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

STAGES = ('consent', 'cv_extracted', 'evidence_connected', 'target_selected', 'readiness_explained', 'project_recommended', 'project_verified', 'rescored', 'feedback_submitted')
REQUIRED = ('participant_id', 'consent', 'cv_extracted', 'evidence_connected', 'target_selected', 'readiness_explained', 'project_recommended', 'project_verified', 'rescored', 'feedback_submitted', 'recommendation_relevant', 'skill_improved', 'willingness_to_pay_eur')
TRUE = {'1', 'true', 'yes'}
FALSE = {'0', 'false', 'no', ''}

def parse_bool(value):
    v = (value or '').strip().lower()
    if v not in TRUE | FALSE:
        raise ValueError(f'invalid boolean: {value!r}')
    return v in TRUE

def analyze(rows):
    seen = set()
    sanitized = []
    for index, row in enumerate(rows, start=2):
        missing = [k for k in REQUIRED if k not in row]
        if missing:
            raise ValueError(f'row {index}: missing columns {missing}')
        uid = (row['participant_id'] or '').strip()
        if not uid or uid in seen:
            raise ValueError(f'row {index}: missing or duplicate participant_id')
        seen.add(uid)
        stages = {s: parse_bool(row[s]) for s in STAGES}
        if not stages['consent']:
            # No consent: exclude entirely from stored/reportable analytics.
            continue
        # Sequence integrity: milestones cannot complete while an earlier stage is absent.
        first_missing = False
        for stage in STAGES:
            if first_missing and stages[stage]:
                raise ValueError(f'row {index}: stage {stage} completed out of order')
            if not stages[stage]:
                first_missing = True
        recommendation = (row['recommendation_relevant'] or '').strip()
        improvement = (row['skill_improved'] or '').strip()
        price_raw = (row['willingness_to_pay_eur'] or '').strip()
        if recommendation and recommendation not in ('1', '2', '3', '4', '5'):
            raise ValueError(f'row {index}: recommendation_relevant should be 1-5')
        if improvement.lower() not in TRUE | FALSE:
            raise ValueError(f'row {index}: invalid skill_improved')
        price = float(price_raw) if price_raw else None
        if price is not None and (price < 0 or price > 10000):
            raise ValueError(f'row {index}: invalid willingness to pay')
        sanitized.append((stages, int(recommendation) if recommendation else None, parse_bool(improvement), price))
    stage_counts = {s: sum(int(item[0][s]) for item in sanitized) for s in STAGES}
    completed = stage_counts['feedback_submitted']
    ratings = [x[1] for x in sanitized if x[1] is not None and x[0]['feedback_submitted']]
    improvements = [x[2] for x in sanitized if x[0]['feedback_submitted']]
    prices = [x[3] for x in sanitized if x[3] is not None and x[0]['feedback_submitted']]
    return {
        'participants_consented': len(sanitized),
        'journeys_completed': completed,
        'pilot_target': 20,
        'target_reached': completed >= 20,
        'stage_counts': stage_counts,
        'recommendation_rating_count': len(ratings),
        'recommendation_relevant_4_or_5_count': sum(x >= 4 for x in ratings),
        'recommendation_relevant_4_or_5_rate': round(sum(x >= 4 for x in ratings) / len(ratings), 3) if ratings else None,
        'self_reported_skill_improvement_count': sum(improvements),
        'improvement_responses': len(improvements),
        'willingness_to_pay_responses': len(prices),
        'willingness_to_pay_median_eur': sorted(prices)[len(prices)//2] if len(prices) % 2 else (sorted(prices)[len(prices)//2-1]+sorted(prices)[len(prices)//2])/2 if prices else None,
        'limitations': ['Self-reported relevance and improvement are not independent skill assessments.', 'Scores and completion must be validated separately using auditable project evidence.', 'No actual users are recruited by this tool.']
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('csv_path', type=Path)
    parser.add_argument('--output', type=Path, default=Path('pilot/report.json'))
    args = parser.parse_args()
    with args.csv_path.open(newline='', encoding='utf-8-sig') as f:
        report = analyze(csv.DictReader(f))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(f"Completed journeys: {report['journeys_completed']}/20; report: {args.output}")
if __name__ == '__main__':
    main()
