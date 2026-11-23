"""Aggregate-only downloads; callers must enforce the result page permissions."""
import csv
import io
import re
import charts


def safe_cell(value):
    text = str(value)
    # Spreadsheet programs can execute formulas even in a quoted CSV cell.
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r', '\n')) else text


def results_csv(result, event, number):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['event_id', 'event_title', 'round', 'method', 'state', 'ballots',
                     'entry_id', 'entry_name', 'score_total_or_votes', 'rating_count', 'average',
                     'rcv_count', 'rcv_votes', 'continuing_ballots', 'exhausted_ballots', 'winner'])
    steps = list(enumerate(result['rounds'], 1)) if result['method'] == 'RCV' else [(None, None)]
    for step_number, step in steps:
        for row in result['rows']:
            writer.writerow([event['id'], safe_cell(event['title']), number, result['method'],
                result['state'], result['ballots'], row['id'], safe_cell(row['name']),
                row['total'] if step is None else '', row['n'] if result['method'] == 'SCORE' else '',
                row['average'] if result['method'] == 'SCORE' and row['average'] is not None else '',
                step_number or '', step['counts'].get(row['id'], '') if step else '',
                step['active'] if step else '', step['exhausted'] if step else '',
                'yes' if result['winner'] == row['id'] else ''])
    return ('\ufeff' + stream.getvalue()).encode('utf-8')


def chart_svg(result, kind='bar', lang='en', rcv_round=None):
    markup = charts.render_chart(result, kind, lang, rcv_round)
    svg = re.search(r'<svg\b.*?</svg>', markup, re.S).group()
    # Standalone SVG needs a natural height as well as a width.
    dims = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg)
    svg = svg.replace(' role="img"', f' height="{dims[2]}" role="img"', 1)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n' + svg).encode('utf-8')
