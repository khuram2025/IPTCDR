"""Report builders + renderers for the scheduled-report engine (P3.1).

A report builder takes (company, start_date, end_date) and returns a dict:
    {'title': str, 'columns': [str, ...], 'rows': [[cell, ...], ...],
     'summary': [(label, value), ...], 'chart': {...}|None}
render_report turns that into bytes in csv / xlsx / pdf / html. Builders reuse the
real KPI functions so scheduled output matches the dashboards exactly. The PDF
renderer is a shared, branded theme (header/footer, KPI cards, charts, styled
tables) so every report type -- and the combined Call Center pack -- looks
professional.
"""
import csv
import io
import logging
from datetime import timedelta

from django.utils import timezone

from acd.kpi import (
    compute_company_callcenter_kpis, real_queue_kpis, agent_productivity,
    format_seconds,
)

logger = logging.getLogger(__name__)

# window key -> resolver returning (start_date, end_date) inclusive, tenant-local.
WINDOWS = {
    'yesterday': 'Yesterday',
    'last_7_days': 'Last 7 days',
    'last_30_days': 'Last 30 days',
    'week_to_date': 'Week to date',
    'month_to_date': 'Month to date',
    'last_month': 'Last month',
}


def resolve_window(window, today=None):
    """Return (start_date, end_date) inclusive for a window key (tenant-local)."""
    today = today or timezone.localdate()
    if window == 'yesterday':
        d = today - timedelta(days=1)
        return d, d
    if window == 'last_7_days':
        return today - timedelta(days=7), today - timedelta(days=1)
    if window == 'last_30_days':
        return today - timedelta(days=30), today - timedelta(days=1)
    if window == 'week_to_date':
        return today - timedelta(days=today.weekday()), today
    if window == 'month_to_date':
        return today.replace(day=1), today
    if window == 'last_month':
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        return last_prev.replace(day=1), last_prev
    # default: yesterday
    d = today - timedelta(days=1)
    return d, d


# --------------------------------------------------------------------------- #
# Builders
# --------------------------------------------------------------------------- #
def _pct(v):
    return '—' if v is None else f"{v}%"


def build_callcenter_summary(company, start, end):
    k = compute_company_callcenter_kpis(company, start, end)
    rows = [
        ['Offered', k['offered']],
        ['Answered', k['answered']],
        ['Abandoned', k['abandoned']],
        ['Answer rate', _pct(k['answer_rate'])],
        ['Abandon rate', _pct(k['abandon_rate'])],
        ['Avg talk time', format_seconds(k['avg_talk_seconds'])],
    ]
    return {
        'title': 'Call Center Summary',
        'columns': ['Metric', 'Value'],
        'rows': rows,
        'summary': [('Offered', k['offered']), ('Answered', k['answered']),
                    ('Answer rate', _pct(k['answer_rate']))],
        'chart': {
            'kind': 'donut', 'title': 'Answered vs Abandoned',
            'labels': ['Answered', 'Abandoned'],
            'series': [{'data': [k['answered'] or 0, k['abandoned'] or 0]}],
        },
        'note': 'Volume from the 3CX socket CDR. Wait-based KPIs (SLA/ASA) are in '
                'the Queue Performance report (real ACD feed).',
    }


def build_queue_performance(company, start, end):
    rq = real_queue_kpis(company, start, end)
    cols = ['Queue', 'DN', 'Calls', 'Answered', 'Answer %', 'Abandon %', 'ASA',
            'Avg Talk', 'Abandoned', 'Avg Wait', 'Longest Wait']
    rows = []
    for q in rq['per_queue']:
        rows.append([
            q['name'], q['dn'], q['calls'], q['answered'], _pct(q['answer_rate']),
            _pct(q['abandon_rate']), format_seconds(q['asa_seconds']),
            format_seconds(q['avg_talk_seconds']), q['abandon_count'],
            format_seconds(q['avg_abandon_wait_seconds']),
            format_seconds(q['max_abandon_wait_seconds']),
        ])
    top = sorted(rq['per_queue'], key=lambda q: q.get('calls') or 0, reverse=True)[:12]
    chart = {
        'kind': 'hbar', 'title': 'Answer % by queue',
        'labels': [(q['name'] or q['dn'])[:18] for q in top],
        'series': [{'data': [round(q['answer_rate'] or 0, 1) for q in top]}],
    } if top else None
    return {
        'title': 'Queue Performance (real ACD)',
        'columns': cols,
        'rows': rows,
        'summary': [('Calls', rq['calls']), ('Answer rate', _pct(rq['answer_rate'])),
                    ('ASA', format_seconds(rq['asa_seconds'])),
                    ('Abandoned', rq['abandon_count'])],
        'chart': chart,
    }


def build_agent_productivity(company, start, end):
    ap = agent_productivity(company, start, end)
    cols = ['Agent', 'DN', 'Answered', 'Lost rings', 'Answer %', 'Talk time',
            'Avg Talk', 'Occupancy %']
    rows = []
    for a in ap['agents']:
        rows.append([
            a['name'], a['dn'], a['answered'], a['lost'], _pct(a['answer_rate']),
            format_seconds(a['talk_seconds']), format_seconds(a['avg_talk_seconds']),
            '—' if a['occupancy_pct'] is None else a['occupancy_pct'],
        ])
    top = sorted(ap['agents'], key=lambda a: a.get('answered') or 0, reverse=True)[:12]
    chart = {
        'kind': 'bar', 'title': 'Answered by agent (top)',
        'labels': [(a['name'] or a['dn'])[:12] for a in top],
        'series': [{'name': 'Answered', 'data': [a['answered'] or 0 for a in top]}],
    } if top else None
    return {
        'title': 'Agent Productivity',
        'columns': cols,
        'rows': rows,
        'summary': [('Agents', ap['agent_count']),
                    ('Answered', ap['total_answered']),
                    ('Lost rings', ap['total_lost'])],
        'chart': chart,
    }


def build_sla_breaches(company, start, end):
    from acd.models import QueueAlert
    qs = (QueueAlert.objects.filter(queue__company=company, stat_date__range=[start, end])
          .select_related('queue').order_by('-stat_date', '-severity'))
    cols = ['Date', 'Severity', 'Queue', 'DN', 'Metric', 'Detail']
    rows = []
    red = amber = 0
    for a in qs:
        red += a.severity == 'red'
        amber += a.severity == 'amber'
        rows.append([str(a.stat_date), a.severity.upper(), a.queue.name,
                     a.queue.external_id, a.get_metric_display(), a.message])
    return {
        'title': 'SLA Breach Alerts',
        'columns': cols,
        'rows': rows,
        'summary': [('Total', len(rows)), ('Red', red), ('Amber', amber)],
        'chart': None,
    }


def build_daily_volume(company, start, end):
    """Per-day call-center volume, served from the materialized rollup (P3.5)."""
    from acd.models import CallDailyRollup
    rows = []
    labels, d_offered, d_answered = [], [], []
    total = ans = miss = 0
    for r in (CallDailyRollup.objects.filter(company=company, day__range=[start, end])
              .order_by('day')):
        total += r.cc_total
        ans += r.cc_answered
        miss += r.cc_missed
        rows.append([str(r.day), r.cc_total, r.cc_answered, r.cc_missed, _pct(r.answer_rate)])
        labels.append(str(r.day)[5:])
        d_offered.append(r.cc_total)
        d_answered.append(r.cc_answered)
    chart = {
        'kind': 'line', 'title': 'Daily volume',
        'labels': labels,
        'series': [{'name': 'Offered', 'data': d_offered},
                   {'name': 'Answered', 'data': d_answered}],
    } if labels else None
    return {
        'title': 'Daily Call Volume',
        'columns': ['Date', 'Offered', 'Answered', 'Missed', 'Answer %'],
        'rows': rows,
        'summary': [('Days', len(rows)), ('Offered', total), ('Answered', ans),
                    ('Answer rate', _pct(round(ans / total * 100, 1) if total else 0))],
        'chart': chart,
    }


def build_cost_by_extension(company, start, end):
    """Outbound call cost grouped by the answering/originating extension."""
    from django.db.models import Count, Sum
    from cdr3cx.models import CallRecord
    qs = (CallRecord.objects.filter(company=company, call_time__date__range=[start, end])
          .exclude(final_dn='').values('final_dn', 'final_dispname')
          .annotate(calls=Count('id'), cost=Sum('total_cost'), dur=Sum('duration'))
          .order_by('-cost')[:200])
    rows, tot_cost, tot_calls = [], 0, 0
    for r in qs:
        cost = round(float(r['cost'] or 0), 3)
        tot_cost += cost
        tot_calls += r['calls']
        rows.append([r['final_dn'], r['final_dispname'] or '', r['calls'],
                     format_seconds(r['dur'] or 0), cost])
    top = rows[:12]
    chart = {
        'kind': 'bar', 'title': 'Top cost by extension',
        'labels': [str(r[0])[:10] for r in top],
        'series': [{'name': 'Cost', 'data': [float(r[4]) for r in top]}],
    } if top else None
    return {
        'title': 'Cost by Extension',
        'columns': ['Extension', 'Name', 'Calls', 'Talk time', 'Cost'],
        'rows': rows,
        'summary': [('Extensions', len(rows)), ('Calls', tot_calls),
                    ('Total cost', round(tot_cost, 2))],
        'chart': chart,
    }


def build_missed_calls_detail(company, start, end):
    """Per-call list of unanswered call-center calls in the window."""
    from cdr3cx.models import CallRecord
    from cdr3cx.callcenter_filters import call_center_call_filter, missed_call_filter
    qs = (CallRecord.objects.filter(company=company, call_time__date__range=[start, end])
          .filter(call_center_call_filter()).filter(missed_call_filter())
          .order_by('-call_time')[:1000])
    rows = []
    for c in qs:
        rows.append([c.call_time.strftime('%Y-%m-%d %H:%M'),
                     c.from_no or c.caller or '', c.to_dn or '',
                     c.to_dispname or '', format_seconds(c.duration or 0)])
    return {
        'title': 'Missed Calls Detail',
        'columns': ['Time', 'Caller', 'To DN', 'Destination', 'Duration'],
        'rows': rows,
        'summary': [('Missed calls', len(rows))],
        'chart': None,
        'note': 'Capped at 1000 most-recent rows.' if len(rows) == 1000 else '',
    }


def build_callcenter_pack(company, start, end):
    """Flagship combined Call Center report: one polished multi-section PDF."""
    summary = build_callcenter_summary(company, start, end)
    queues = build_queue_performance(company, start, end)
    agents = build_agent_productivity(company, start, end)
    sla = build_sla_breaches(company, start, end)
    rq = real_queue_kpis(company, start, end)
    top = list(summary['summary'])
    if rq.get('available'):
        top += [('ASA', format_seconds(rq.get('asa_seconds'))),
                ('Abandon rate', _pct(rq.get('abandon_rate')))]
    return {
        'title': 'Call Center Report',
        'sections': [summary, queues, agents, sla],
        'summary': top[:5],
        # Fallbacks so csv/xlsx/html still produce the summary section.
        'columns': summary['columns'],
        'rows': summary['rows'],
        'chart': summary.get('chart'),
        'note': 'Combined report — the PDF contains all sections '
                '(summary, queues, agents, SLA).',
    }


def build_survey_summary(company, start, end):
    from surveys.services.metrics import survey_dashboard_metrics
    m = survey_dashboard_metrics(company, start, end)
    rows = [
        ['Total responses', m['total_responses']],
        ['Matched to calls', m['matched_responses']],
        ['Match rate', _pct(m['match_rate'])],
        ['CSAT (top-box 4–5)', _pct(m['csat']['csat_pct'])],
        ['Average rating', m['csat']['avg_rating'] or '—'],
        ['Issue resolved rate', _pct(m['solved']['solved_pct'])],
        ['NPS', m['nps']['nps_score'] if m['nps']['nps_score'] is not None else '—'],
    ]
    for q in m.get('by_queue', []):
        rows.append([f"Queue: {q['queue_name']}", f"CSAT {_pct(q['csat_pct'])} ({q['count']} responses)"])
    return {
        'title': 'Survey Summary (CSAT)',
        'columns': ['Metric', 'Value'],
        'rows': rows,
        'summary': [('CSAT', _pct(m['csat']['csat_pct'])), ('Responses', m['total_responses'])],
        'chart': None,
        'note': 'Post-call IVR survey data from 3CX CFD ingest.',
    }


REPORT_TYPES = {
    'callcenter_pack': ('Call Center Report', build_callcenter_pack),
    'callcenter_summary': ('Call Center Summary', build_callcenter_summary),
    'queue_performance': ('Queue Performance (real ACD)', build_queue_performance),
    'agent_productivity': ('Agent Productivity', build_agent_productivity),
    'sla_breaches': ('SLA Breach Alerts', build_sla_breaches),
    'daily_volume': ('Daily Call Volume', build_daily_volume),
    'cost_by_extension': ('Cost by Extension', build_cost_by_extension),
    'missed_calls_detail': ('Missed Calls Detail', build_missed_calls_detail),
    'survey_summary': ('Survey Summary (CSAT)', build_survey_summary),
}

REPORT_DESCRIPTIONS = {
    'callcenter_pack': 'Complete call-center report: KPI overview plus queue performance, '
                       'agent productivity and SLA breaches in one document.',
    'callcenter_summary': 'Offered / answered / abandoned volume and answer rate for the company.',
    'queue_performance': 'Per-queue real ACD: answer rate, ASA, abandonment and wait — from the 3CX XAPI.',
    'agent_productivity': 'Per-agent answered vs lost rings, answer rate, talk time and occupancy.',
    'sla_breaches': 'Tiered amber/red SLA-breach alerts fired in the period.',
    'daily_volume': 'Day-by-day call-center volume (rollup-backed, fast).',
    'cost_by_extension': 'Outbound call cost and talk time grouped by extension.',
    'missed_calls_detail': 'Per-call list of unanswered call-center calls.',
    'survey_summary': 'CSAT, solved rate, and per-queue survey breakdown from post-call IVR.',
}


def build_report(report_type, company, start, end):
    if report_type not in REPORT_TYPES:
        raise ValueError(f'Unknown report_type: {report_type}')
    data = REPORT_TYPES[report_type][1](company, start, end)
    data.setdefault('note', '')
    data.setdefault('chart', None)
    data['report_type'] = report_type
    data['company'] = company.name
    data['period'] = f'{start} to {end}'
    return data


# --------------------------------------------------------------------------- #
# Renderers
# --------------------------------------------------------------------------- #
_MIME = {
    'csv': 'text/csv',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'pdf': 'application/pdf',
    'html': 'text/html',
}

# Brand palette
_BRAND = '#405189'
_PANEL = '#f4f6fb'
_GRID = '#cfd6e6'
_INK = '#2a3142'
_MUTE = '#878a99'


def _render_csv(d):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([d['title']])
    w.writerow([f"{d['company']} — {d['period']}"])
    w.writerow([])
    w.writerow(d['columns'])
    for r in d['rows']:
        w.writerow(r)
    if d['summary']:
        w.writerow([])
        for label, val in d['summary']:
            w.writerow([label, val])
    return buf.getvalue().encode('utf-8')


def _render_xlsx(d):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = Workbook()
    ws = wb.active
    ws.title = d['title'][:31]
    head = Font(bold=True, color='FFFFFF')
    fill = PatternFill('solid', fgColor='405189')
    ws.append([d['title']])
    ws['A1'].font = Font(bold=True, size=14)
    ws.append([f"{d['company']} — {d['period']}"])
    ws.append([])
    ws.append(d['columns'])
    hdr_row = ws.max_row
    for cell in ws[hdr_row]:
        cell.font = head
        cell.fill = fill
        cell.alignment = Alignment(horizontal='left')
    for r in d['rows']:
        ws.append(r)
    if d['summary']:
        ws.append([])
        ws.append(['Summary'])
        ws[f'A{ws.max_row}'].font = Font(bold=True)
        for label, val in d['summary']:
            ws.append([label, val])
    for col in ws.columns:
        width = max((len(str(c.value)) for c in col if c.value is not None), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(width + 3, 48)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


# ----- professional PDF theme ----------------------------------------------- #
def _logo_path():
    import os
    try:
        from django.conf import settings
        p = os.path.join(settings.STATIC_ROOT or '', 'images', 'logo-dark.png')
        if os.path.exists(p):
            return p
    except Exception:
        pass
    return None


def _make_canvas(company):
    """Two-pass canvas factory that stamps a branded header + 'Page X of Y' footer."""
    from reportlab.pdfgen import canvas as _canvas
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    brand = colors.HexColor(_BRAND)
    ts = timezone.localtime().strftime('%d %b %Y, %H:%M')

    class NumberedCanvas(_canvas.Canvas):
        def __init__(self, *a, **k):
            _canvas.Canvas.__init__(self, *a, **k)
            self._saved = []

        def showPage(self):
            self._saved.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            n = len(self._saved)
            for st in self._saved:
                self.__dict__.update(st)
                self._hf(n)
                _canvas.Canvas.showPage(self)
            _canvas.Canvas.save(self)

        def _hf(self, page_count):
            w, h = self._pagesize
            # header band — company name is the brand (no template logo)
            self.setFillColor(brand)
            self.rect(0, h - 1.15 * cm, w, 1.15 * cm, stroke=0, fill=1)
            self.setFillColor(colors.white)
            self.setFont('Helvetica-Bold', 11)
            self.drawString(1.0 * cm, h - 0.77 * cm, company or 'Report')
            self.setFont('Helvetica', 8)
            self.drawRightString(w - 1.0 * cm, h - 0.77 * cm, f'Generated {ts}')
            # footer
            self.setStrokeColor(colors.HexColor(_GRID))
            self.setLineWidth(0.5)
            self.line(1.0 * cm, 1.05 * cm, w - 1.0 * cm, 1.05 * cm)
            self.setFillColor(colors.HexColor(_MUTE))
            self.setFont('Helvetica', 7.5)
            self.drawString(1.0 * cm, 0.66 * cm, f'Confidential · {company}')
            self.drawRightString(w - 1.0 * cm, 0.66 * cm,
                                 f'Page {self._pageNumber} of {page_count}')

    return NumberedCanvas


def _pdf_styles():
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT
    from reportlab.lib import colors
    ss = getSampleStyleSheet()
    return {
        'title': ParagraphStyle('zT', parent=ss['Title'], fontSize=19,
                                textColor=colors.HexColor(_INK), alignment=TA_LEFT,
                                spaceAfter=1),
        'subtitle': ParagraphStyle('zS', parent=ss['Normal'], fontSize=10,
                                   textColor=colors.HexColor(_BRAND), spaceAfter=2),
        'section': ParagraphStyle('zSec', parent=ss['Heading2'], fontSize=13,
                                  textColor=colors.HexColor(_BRAND), spaceBefore=8,
                                  spaceAfter=5),
        'note': ParagraphStyle('zN', parent=ss['Normal'], fontSize=8,
                               textColor=colors.HexColor(_MUTE)),
        'cell': ParagraphStyle('zC', parent=ss['Normal'], fontSize=8, leading=10),
        'cellr': ParagraphStyle('zCR', parent=ss['Normal'], fontSize=8, leading=10,
                                alignment=TA_RIGHT),
        'kpi': ParagraphStyle('zK', parent=ss['Normal'], fontSize=8, leading=18,
                              alignment=1),
    }


def _is_num(v):
    s = str(v).strip()
    if not s or s == '—':
        return False
    s2 = s.replace(',', '').replace('%', '').replace(' SAR', '')
    try:
        float(s2)
        return True
    except ValueError:
        if ':' in s2 and all(p.isdigit() for p in s2.split(':') if p != ''):
            return True
        return False


def _kpi_band(summary, styles, total_width):
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib import colors
    if not summary:
        return None
    cells = [Paragraph(
        f'<b><font size="15" color="{_INK}">{v}</font></b><br/>'
        f'<font size="7.5" color="{_MUTE}">{str(l).upper()}</font>', styles['kpi'])
        for l, v in summary]
    n = len(cells)
    t = Table([cells], colWidths=[total_width / n] * n)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(_PANEL)),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor(_GRID)),
        ('INNERGRID', (0, 0), (-1, -1), 1.5, colors.white),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    return t


def _styled_table(columns, rows, styles, total_width):
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    ncol = len(columns)
    numeric = [True] * ncol
    for r in (rows[:25] or []):
        for i, c in enumerate(r):
            if i < ncol and not _is_num(c):
                numeric[i] = False
    head = [Paragraph(f'<b><font color="white">{c}</font></b>', styles['cell'])
            for c in columns]
    body = []
    if not rows:
        body = [[Paragraph('(no data)', styles['cell'])] + [''] * (ncol - 1)]
    else:
        for r in rows:
            row = []
            for i in range(ncol):
                c = r[i] if i < len(r) else ''
                st = styles['cellr'] if numeric[i] else styles['cell']
                row.append(Paragraph(str(c), st))
            body.append(row)
    eff = total_width if ncol > 4 else min(total_width, ncol * 4.6 * cm)
    weights = [1.7] + [1.0] * (ncol - 1)
    tot = sum(weights)
    cw = [eff * w / tot for w in weights]
    t = Table([head] + body, colWidths=cw, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(_BRAND)),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor(_GRID)),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor(_PANEL)]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    return t


def _draw_chart(spec, width, height):
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.graphics.charts.barcharts import VerticalBarChart, HorizontalBarChart
    from reportlab.graphics.charts.linecharts import HorizontalLineChart
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.lib import colors
    palette = [colors.HexColor('#405189'), colors.HexColor('#0ab39c'),
               colors.HexColor('#f06548'), colors.HexColor('#f7b84b'),
               colors.HexColor('#299cdb')]
    d = Drawing(width, height)
    kind = spec.get('kind')
    labels = [str(x) for x in spec.get('labels', [])]
    series = spec.get('series', [])
    if spec.get('title'):
        d.add(String(6, height - 11, spec['title'], fontSize=9,
                     fillColor=colors.HexColor(_INK)))
    _flat = [float(v or 0) for s in series for v in (s.get('data') or [])]
    if kind != 'donut' and (not labels or not any(_flat)):
        d.add(String(6, height / 2, 'No data for this period', fontSize=9,
                     fillColor=colors.HexColor(_MUTE)))
        return d
    if kind == 'donut':
        vals = [max(0.0, float(x or 0)) for x in (series[0]['data'] if series else [])]
        if sum(vals) <= 0:
            d.add(String(6, height / 2, 'No data for this period', fontSize=9,
                         fillColor=colors.HexColor(_MUTE)))
            return d
        pie = Pie()
        pie.x = width / 2 - 45
        pie.y = 8
        pie.width = 90
        pie.height = 90
        pie.data = vals
        pie.labels = [str(x) for x in labels] or ['']
        pie.innerRadiusFraction = 0.55
        pie.sideLabels = 1
        for i in range(len(pie.data)):
            pie.slices[i].fillColor = palette[i % len(palette)]
        pie.slices.strokeColor = colors.white
        pie.slices.strokeWidth = 1
        d.add(pie)
    elif kind == 'hbar':
        bc = HorizontalBarChart()
        bc.x = 95
        bc.y = 12
        bc.width = width - 115
        bc.height = height - 30
        bc.data = [series[0]['data']] if series else [[]]
        bc.categoryAxis.categoryNames = labels
        bc.bars[0].fillColor = palette[0]
        bc.valueAxis.valueMin = 0
        bc.categoryAxis.labels.fontSize = 7
        bc.valueAxis.labels.fontSize = 6
        d.add(bc)
    elif kind == 'line':
        lc = HorizontalLineChart()
        lc.x = 32
        lc.y = 22
        lc.width = width - 50
        lc.height = height - 42
        lc.data = [s['data'] for s in series] or [[]]
        lc.categoryAxis.categoryNames = labels
        for i in range(len(lc.data)):
            lc.lines[i].strokeColor = palette[i % len(palette)]
            lc.lines[i].strokeWidth = 1.5
        lc.categoryAxis.labels.fontSize = 6
        lc.categoryAxis.labels.angle = 30
        lc.categoryAxis.labels.boxAnchor = 'ne'
        lc.valueAxis.labels.fontSize = 6
        d.add(lc)
    else:  # bar
        bc = VerticalBarChart()
        bc.x = 32
        bc.y = 24
        bc.width = width - 50
        bc.height = height - 44
        bc.data = [s['data'] for s in series] or [[]]
        bc.categoryAxis.categoryNames = labels
        for i in range(len(bc.data)):
            bc.bars[i].fillColor = palette[i % len(palette)]
        bc.valueAxis.valueMin = 0
        bc.categoryAxis.labels.fontSize = 6
        bc.categoryAxis.labels.angle = 30
        bc.categoryAxis.labels.boxAnchor = 'ne'
        bc.valueAxis.labels.fontSize = 6
        d.add(bc)
    return d


def _section_flowables(s, styles, tw, heading=False, include_charts=True):
    from reportlab.platypus import Paragraph, Spacer
    out = []
    if heading:
        out.append(Paragraph(s['title'], styles['section']))
    if s.get('summary'):
        out.append(_kpi_band(s['summary'], styles, tw))
        out.append(Spacer(1, 6))
    if include_charts and s.get('chart'):
        out.append(_draw_chart(s['chart'], tw, 150))
        out.append(Spacer(1, 6))
    out.append(_styled_table(s['columns'], s['rows'], styles, tw))
    if s.get('note'):
        out.append(Spacer(1, 4))
        out.append(Paragraph('<i>' + s['note'] + '</i>', styles['note']))
    return out


def _render_pdf(d):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

    styles = _pdf_styles()
    sections = d.get('sections')
    all_cols = [len(d.get('columns', []))] + [len(s.get('columns', []))
                                              for s in (sections or [])]
    wide = max(all_cols) > 6
    pagesize = landscape(A4) if wide else A4

    def _build(include_charts):
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=pagesize, topMargin=1.7 * cm,
                                bottomMargin=1.5 * cm, leftMargin=1.2 * cm,
                                rightMargin=1.2 * cm, title=d.get('title', 'Report'))
        tw = doc.width
        story = [Paragraph(d['title'], styles['title']),
                 Paragraph(f"{d['company']} &nbsp;·&nbsp; {d['period']}", styles['subtitle'])]
        desc = REPORT_DESCRIPTIONS.get(d.get('report_type', ''), '')
        if desc:
            story.append(Paragraph(desc, styles['note']))
        story.append(Spacer(1, 8))
        if d.get('summary'):
            story.append(_kpi_band(d['summary'], styles, tw))
            story.append(Spacer(1, 10))
        if sections:
            for i, s in enumerate(sections):
                story.extend(_section_flowables(s, styles, tw, heading=True,
                                                 include_charts=include_charts))
                if i < len(sections) - 1:
                    story.append(Spacer(1, 12))
        else:
            if include_charts and d.get('chart'):
                story.append(_draw_chart(d['chart'], tw, 160))
                story.append(Spacer(1, 8))
            story.append(_styled_table(d['columns'], d['rows'], styles, tw))
            if d.get('note'):
                story.append(Spacer(1, 6))
                story.append(Paragraph('<i>' + d['note'] + '</i>', styles['note']))
        doc.build(story, canvasmaker=_make_canvas(d['company']))
        return buf.getvalue()

    try:
        return _build(include_charts=True)
    except Exception:
        logger.warning('PDF chart render failed (%s); rebuilding without charts',
                       d.get('report_type'), exc_info=True)
        return _build(include_charts=False)


def _render_html(d):
    from django.template.loader import render_to_string
    return render_to_string('cdr/reports/report.html', {'d': d}).encode('utf-8')


_RENDERERS = {'csv': _render_csv, 'xlsx': _render_xlsx, 'pdf': _render_pdf, 'html': _render_html}


def render_report(data, fmt):
    """Return (bytes, mime, ext) for the given report data and format."""
    if fmt not in _RENDERERS:
        raise ValueError(f'Unknown format: {fmt}')
    return _RENDERERS[fmt](data), _MIME[fmt], fmt
