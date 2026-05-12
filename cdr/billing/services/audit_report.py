"""Free toll-fraud audit — lead-generation tool.

Accepts a CSV of CDRs from a prospect, runs them through a built-in rule pack,
and produces a branded PDF report with findings + remediation suggestions.

CSV format (column names case-insensitive, all but ``call_time`` and ``callee``
optional):
    call_time, caller, callee, duration, total_cost, country

Outputs an in-memory PDF byte string. Stores no CDR data — used purely for the
audit response.
"""
from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak,
)

from .country import iso_country

# -----------------------------------------------------------------
# Built-in audit rules — opinionated defaults to surface common issues
# -----------------------------------------------------------------

PREMIUM_COUNTRIES = {'CU', 'KP', 'SO', 'XK', 'PG', 'AO', 'BI', 'MD', 'CF', 'TL'}
BUSINESS_HOURS = (time(8, 0), time(18, 0))


def _parse_dt(value: str):
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M'):
        try:
            return datetime.strptime(value.strip(), fmt)
        except (ValueError, TypeError):
            continue
    return None


def _parse_decimal(value: str):
    try:
        return Decimal(str(value).strip() or '0')
    except (InvalidOperation, ValueError):
        return Decimal('0')


def _parse_int(value: str):
    try:
        return int(float(str(value).strip() or '0'))
    except (TypeError, ValueError):
        return 0


def parse_cdr_csv(file_obj) -> list[dict]:
    """Parse a CSV-of-CDRs into a list of normalized dicts."""
    text = file_obj.read()
    if isinstance(text, bytes):
        text = text.decode('utf-8-sig', errors='replace')
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for raw in reader:
        # Lower-case keys for tolerance
        row = {(k or '').strip().lower(): (v or '').strip() for k, v in raw.items()}
        if not row.get('callee'):
            continue
        rows.append({
            'call_time': _parse_dt(row.get('call_time', '')),
            'caller':    row.get('caller', ''),
            'callee':    row.get('callee', ''),
            'duration':  _parse_int(row.get('duration', '0')),
            'total_cost': _parse_decimal(row.get('total_cost', '0') or row.get('cost', '0')),
            'country':   row.get('country', ''),
        })
    return rows


def analyze(rows: list[dict]) -> dict:
    """Run audit rules. Returns ``{summary, findings, recommendations}``."""
    if not rows:
        return {
            'summary': {'total_calls': 0, 'total_cost': Decimal('0'), 'period': '—'},
            'findings': [],
            'recommendations': [],
            'top_countries': [],
            'top_callers': [],
        }

    findings = []
    total_cost = sum((r['total_cost'] for r in rows), Decimal('0'))
    intl_calls = [r for r in rows if (iso_country(r['callee']) or 'SA') != 'SA']
    intl_cost = sum((r['total_cost'] for r in intl_calls), Decimal('0'))

    times = [r['call_time'] for r in rows if r['call_time']]
    period = '—'
    if times:
        period = f"{min(times):%Y-%m-%d} → {max(times):%Y-%m-%d}"

    # Finding 1 — premium / high-risk destinations
    premium = [r for r in intl_calls if (iso_country(r['callee']) or '') in PREMIUM_COUNTRIES]
    if premium:
        findings.append({
            'severity': 'critical',
            'title': f"Calls to premium / high-risk destinations ({len(premium)})",
            'detail': f"Total cost on premium destinations: {sum((r['total_cost'] for r in premium), Decimal('0')):.2f}. "
                      "These countries are commonly abused for International Revenue Share Fraud.",
            'sample': [(r['callee'], iso_country(r['callee']) or '?', f"{r['total_cost']:.2f}") for r in premium[:5]],
        })

    # Finding 2 — after-hours intl
    after_hours = [
        r for r in intl_calls
        if r['call_time'] and not (BUSINESS_HOURS[0] <= r['call_time'].time() < BUSINESS_HOURS[1])
    ]
    if after_hours:
        findings.append({
            'severity': 'high' if len(after_hours) > 10 else 'medium',
            'title': f"After-hours international calls ({len(after_hours)})",
            'detail': f"{len(after_hours)} international calls placed outside 08:00–18:00. "
                      "After-hours intl traffic is a classic fraud signal.",
            'sample': [(r['callee'], r['call_time'].strftime('%Y-%m-%d %H:%M'), f"{r['total_cost']:.2f}")
                       for r in after_hours[:5]],
        })

    # Finding 3 — long international calls (>30 min)
    long_intl = [r for r in intl_calls if r['duration'] >= 1800]
    if long_intl:
        findings.append({
            'severity': 'high',
            'title': f"Unusually long international calls ({len(long_intl)})",
            'detail': "Calls over 30 minutes to international destinations frequently indicate "
                      "automated fraud (call generators, premium-rate hijacking).",
            'sample': [(r['callee'], f"{r['duration']//60} min", f"{r['total_cost']:.2f}") for r in long_intl[:5]],
        })

    # Finding 4 — extension velocity (>50 calls or >SAR 500 in any single calendar day)
    by_caller_day = defaultdict(lambda: {'calls': 0, 'cost': Decimal('0')})
    for r in rows:
        if not r['call_time'] or not r['caller']:
            continue
        key = (r['caller'], r['call_time'].date())
        by_caller_day[key]['calls'] += 1
        by_caller_day[key]['cost'] += r['total_cost']
    velocity_hits = [(c, d, v) for (c, d), v in by_caller_day.items()
                     if v['calls'] >= 50 or v['cost'] >= 500]
    if velocity_hits:
        findings.append({
            'severity': 'high',
            'title': f"Extensions with extreme daily activity ({len(velocity_hits)} extension-days)",
            'detail': "Single extension placed ≥50 calls or generated ≥SAR 500 in one day. "
                      "Often indicates compromised credentials or auto-dialer abuse.",
            'sample': [(c, d.isoformat(), f"{v['calls']} calls / {v['cost']:.2f}") for c, d, v in velocity_hits[:5]],
        })

    # Top countries / callers (informational tables)
    country_counter = Counter()
    caller_counter = Counter()
    for r in rows:
        iso = iso_country(r['callee']) or 'unknown'
        country_counter[iso] += 1
        if r['caller']:
            caller_counter[r['caller']] += 1
    top_countries = country_counter.most_common(8)
    top_callers = caller_counter.most_common(8)

    # Recommendations always relevant
    recommendations = [
        "Enable real-time fraud rules covering: international spike, after-hours intl, "
        "premium destinations, per-extension cost velocity.",
        "Set per-extension daily cost limits with auto-disable on breach.",
        "Restrict international dialing to a whitelist of approved destinations.",
        "Enforce strong SIP credentials + IP whitelisting on all PBX endpoints.",
        "Subscribe to webhook alerts so your team learns about fraud in seconds, not days.",
    ]
    if not findings:
        recommendations.insert(0, "No high-confidence fraud patterns detected in this dataset. "
                                  "We recommend ongoing monitoring — fraud often only appears for short bursts.")

    return {
        'summary': {
            'total_calls':  len(rows),
            'total_cost':   total_cost,
            'intl_calls':   len(intl_calls),
            'intl_cost':    intl_cost,
            'period':       period,
        },
        'findings': findings,
        'recommendations': recommendations,
        'top_countries': top_countries,
        'top_callers': top_callers,
    }


def render_pdf(report: dict, *, contact_name: str = '', contact_company: str = '',
               brand: str = 'IPT Portal') -> bytes:
    """Render the audit dictionary as a branded PDF and return the bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm,
                            title=f"{brand} — Free Toll-Fraud Audit")
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle('h1', parent=styles['Heading1'], fontSize=20, spaceAfter=12,
                        textColor=colors.HexColor('#1f2937'))
    h2 = ParagraphStyle('h2', parent=styles['Heading2'], fontSize=14, spaceAfter=8,
                        textColor=colors.HexColor('#1f2937'))
    body = ParagraphStyle('body', parent=styles['BodyText'], fontSize=10, leading=14)
    muted = ParagraphStyle('muted', parent=body, textColor=colors.HexColor('#6b7280'))

    story = []
    story.append(Paragraph(f"<b>{brand}</b> · Free Toll-Fraud Audit", h1))
    if contact_company or contact_name:
        story.append(Paragraph(f"Prepared for: <b>{contact_company or contact_name}</b>", body))
    story.append(Paragraph(f"Generated: {datetime.utcnow():%Y-%m-%d %H:%M UTC}", muted))
    story.append(Spacer(1, 0.4*cm))

    # Summary table
    summary = report['summary']
    story.append(Paragraph("Dataset summary", h2))
    summary_rows = [
        ['Period analysed',    summary['period']],
        ['Total calls',        f"{summary['total_calls']:,}"],
        ['Total cost',         f"{summary.get('total_cost', 0):,.2f}"],
        ['International calls', f"{summary.get('intl_calls', 0):,}"],
        ['International cost', f"{summary.get('intl_cost', 0):,.2f}"],
    ]
    t = Table(summary_rows, colWidths=[6*cm, 9*cm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e5e7eb')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.6*cm))

    # Findings
    story.append(Paragraph("Findings", h2))
    findings = report['findings']
    if not findings:
        story.append(Paragraph(
            "No high-confidence fraud patterns surfaced in this dataset. "
            "<b>Note:</b> fraud is often episodic — continuous monitoring is recommended.", body))
    else:
        sev_color = {
            'critical': colors.HexColor('#dc2626'),
            'high':     colors.HexColor('#f97316'),
            'medium':   colors.HexColor('#0891b2'),
            'low':      colors.HexColor('#6b7280'),
        }
        for f in findings:
            badge = f"<font color='{sev_color[f['severity']].hexval()}'><b>[{f['severity'].upper()}]</b></font>"
            story.append(Paragraph(f"{badge} &nbsp; {f['title']}", body))
            story.append(Paragraph(f['detail'], muted))
            if f.get('sample'):
                rows = [['Sample', '', '']] + list(f['sample'])
                tbl = Table(rows, colWidths=[5*cm, 4*cm, 4*cm])
                tbl.setStyle(TableStyle([
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('GRID', (0, 1), (-1, -1), 0.25, colors.HexColor('#e5e7eb')),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ]))
                story.append(Spacer(1, 0.15*cm))
                story.append(tbl)
            story.append(Spacer(1, 0.4*cm))

    # Recommendations
    story.append(Paragraph("Recommendations", h2))
    for i, rec in enumerate(report['recommendations'], 1):
        story.append(Paragraph(f"{i}. {rec}", body))
    story.append(Spacer(1, 0.6*cm))

    # Top countries / callers
    if report['top_countries']:
        story.append(Paragraph("Top destinations (by call count)", h2))
        rows = [['Country', 'Calls']] + [[c, str(n)] for c, n in report['top_countries']]
        tbl = Table(rows, colWidths=[6*cm, 4*cm])
        tbl.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e5e7eb')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ]))
        story.append(tbl)

    story.append(Spacer(1, 0.8*cm))
    story.append(Paragraph(
        "<b>Want continuous protection?</b> IPT Portal can run these checks in real-time on every "
        "call from any PBX (3CX, Cisco CUCM, MS Teams, Webex, Zoom). "
        "Reach out to the team for a demo.", body))

    doc.build(story)
    return buf.getvalue()
