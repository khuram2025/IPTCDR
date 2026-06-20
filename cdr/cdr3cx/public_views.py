"""Public marketing site (SEO-optimised, no auth) for connect.zentryc.com."""
import logging

from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_safe

logger = logging.getLogger(__name__)

SITE = 'https://connect.zentryc.com'
PRICING_EMAIL = 'info@zentryc.com'
SUPPORT_EMAIL = 'support@zentryc.com'

SOLUTION_PAGES = {
    '3cx-billing-quota': {
        'slug': '3cx-billing-quota',
        'title': '3CX Billing Quota Software | Per-Extension Call Spend Control | Zentryc',
        'meta_description': (
            'Control 3CX Billing Quota by extension with call rates, live usage, '
            'low-balance alerts, invoices and automatic 3CX external-call blocking.'
        ),
        'meta_keywords': (
            '3CX Billing Quota, 3CX quota billing, 3CX billing software, 3CX call accounting, '
            '3CX call quota, extension call quota, 3CX external call blocking, VoIP billing quota'
        ),
        'og_title': '3CX Billing Quota Software for Extension Spend Control',
        'og_description': 'Per-extension call quotas, 3CX call accounting, invoices and automatic external-call control in one portal.',
        'eyebrow': '3CX Billing Quota',
        'headline': 'Control every 3CX extension budget before the bill arrives',
        'subhead': (
            'Zentryc turns 3CX call detail records into live billing quota controls: '
            'rate each call, deduct usage from the right extension, alert teams before '
            'overspend and block external calls when a quota is exhausted.'
        ),
        'screenshot': 'images/solutions/real-3cx-billing-quota.jpg',
        'screenshot_alt': 'Authenticated Zentryc quota usage dashboard with extension totals, low balance, exhausted quota and external-call blocking filters.',
        'primary_keyword': '3CX Billing Quota',
        'supporting_keywords': [
            '3CX call accounting',
            '3CX quota billing',
            'extension call quota',
            '3CX external call blocking',
            'VoIP billing control',
        ],
        'snippet': {
            'title': 'Quota Usage Dashboard',
            'metrics': [
                {'label': 'Extensions tracked', 'value': '286', 'tone': 'info'},
                {'label': 'Low balance', 'value': '14', 'tone': 'warn'},
                {'label': 'Blocked', 'value': '6', 'tone': 'danger'},
            ],
            'rows': [
                {'label': 'Sales 214', 'value': 'SAR 41.20 left', 'tone': 'warn'},
                {'label': 'Support 118', 'value': 'External allowed', 'tone': 'ok'},
                {'label': 'Finance 037', 'value': 'Monthly reset ready', 'tone': 'info'},
            ],
        },
        'proof_points': [
            'Daily, weekly or monthly quota reset cycles',
            'Per-extension remaining balance and used amount',
            'Call rates by local, mobile, national and international pattern',
            'Low-balance and exhausted-quota filtering',
            '3CX API enforcement for external-call blocking',
        ],
        'sections': [
            {
                'heading': 'Real 3CX call cost, not spreadsheet estimates',
                'text': (
                    'Every 3CX call record is categorized against tenant-owned call patterns '
                    'and rated per minute. Zentryc calculates total cost, updates extension '
                    'usage and keeps the billing view aligned with the same records used for '
                    'analytics and reporting.'
                ),
                'bullets': [
                    'Match prefixes and regex rules for local, mobile, national and international calls',
                    'Round duration consistently for billing and invoice reconciliation',
                    'Separate usage by tenant, extension, caller and call category',
                ],
            },
            {
                'heading': 'Quota enforcement with 3CX call control',
                'text': (
                    'When a balance reaches zero, Zentryc can enforce the state through the '
                    'owning tenant 3CX XAPI credentials. The portal records who is exhausted, '
                    'who is blocked and which extensions need more balance before they can '
                    'place external calls again.'
                ),
                'bullets': [
                    'Use tenant-specific 3CX API credentials, never shared PBX credentials',
                    'Block or allow external calls on state changes only',
                    'Top up custom balances when management approves additional spend',
                ],
            },
            {
                'heading': 'Billing visibility for finance and operations',
                'text': (
                    'Finance teams see the same usage supervisors see. That means fewer billing '
                    'disputes, faster chargeback reporting and clearer accountability for each '
                    'department, branch or extension owner.'
                ),
                'bullets': [
                    'Filter by quota plan, balance status, blocked status and extension search',
                    'Export usage for internal chargeback or customer billing',
                    'Tie quotas to multi-currency billing and tax rules',
                ],
            },
        ],
        'faq': [
            {
                'question': 'Can Zentryc block 3CX external calls automatically?',
                'answer': 'Yes. When quota enforcement is enabled, Zentryc can use tenant-specific 3CX XAPI credentials to block or unblock external calling for an extension based on its quota balance.',
            },
            {
                'question': 'Can quotas reset monthly, weekly or daily?',
                'answer': 'Yes. Quota plans can reset on daily, weekly or monthly cycles, with remaining balance and used amount tracked per extension.',
            },
            {
                'question': 'Does this support chargeback billing?',
                'answer': 'Yes. Rated call costs, extension usage and quota status can be used for departmental chargeback, tenant billing and invoice reconciliation.',
            },
        ],
    },
    '3cx-setup': {
        'slug': '3cx-setup',
        'title': '3CX Setup for Reporting, Billing & Call Center Analytics | Zentryc',
        'meta_description': (
            'Set up 3CX CDR, XAPI, extension sync, queues, billing rules, quotas, '
            'wallboards and scheduled reports in Zentryc.'
        ),
        'meta_keywords': (
            '3CX setup, 3CX reporting setup, 3CX billing setup, 3CX XAPI setup, 3CX CDR setup, '
            '3CX call center setup, 3CX integration, Zentryc setup'
        ),
        'og_title': '3CX Setup for Analytics, Billing and Call Center Reporting',
        'og_description': 'Connect 3CX CDR, XAPI, extensions, queues, billing rules and reports to Zentryc with a clean deployment path.',
        'eyebrow': '3CX Setup',
        'headline': 'Set up 3CX reporting, billing and call-center intelligence in one portal',
        'subhead': (
            'Zentryc gives 3CX administrators a structured path from raw PBX data to '
            'production dashboards: CDR ingestion, XAPI queue data, synced extensions, '
            'tenant security, billing rules, quotas, alerts and scheduled reports.'
        ),
        'screenshot': 'images/solutions/real-3cx-setup.jpg',
        'screenshot_alt': 'Authenticated Zentryc extensions setup view with 3CX sync status, registration filters and external-call controls.',
        'primary_keyword': '3CX Setup',
        'supporting_keywords': [
            '3CX CDR setup',
            '3CX XAPI setup',
            '3CX reporting setup',
            '3CX billing setup',
            '3CX call center setup',
        ],
        'snippet': {
            'title': '3CX Integration Checklist',
            'metrics': [
                {'label': 'CDR feed', 'value': 'Live', 'tone': 'ok'},
                {'label': 'XAPI queues', 'value': 'Synced', 'tone': 'ok'},
                {'label': 'Reports', 'value': 'Scheduled', 'tone': 'info'},
            ],
            'rows': [
                {'label': 'Extensions', 'value': 'Users mapped', 'tone': 'ok'},
                {'label': 'Call patterns', 'value': 'Rates active', 'tone': 'info'},
                {'label': 'Wallboard', 'value': 'Ready for supervisors', 'tone': 'ok'},
            ],
        },
        'proof_points': [
            '3CX CDR feed and tenant listening-port configuration',
            '3CX XAPI details for real queue and extension data',
            'Extension directory sync and PBX user mapping',
            'Call patterns, rates, quotas and billing setup',
            'Public knowledge-base guide for 3CX survey integration',
        ],
        'sections': [
            {
                'heading': 'Start with secure CDR ingestion',
                'text': (
                    'Zentryc can isolate tenants by company, listening port and allowed PBX '
                    'source IPs. Once the 3CX call feed is connected, records are normalized '
                    'into one reporting and billing model.'
                ),
                'bullets': [
                    'Map each tenant to the right company and data boundary',
                    'Preserve original call facts while calculating business metrics',
                    'Keep dashboards, billing and reports on the same source of truth',
                ],
            },
            {
                'heading': 'Add XAPI for better queue and user intelligence',
                'text': (
                    'For call centers, the 3CX XAPI unlocks queue and user details that basic '
                    'CDR exports cannot provide. Zentryc uses those details for real ACD KPIs, '
                    'agent mapping and extension control.'
                ),
                'bullets': [
                    'Sync 3CX users and extension metadata',
                    'Pull detailed queue statistics for service level and ASA',
                    'Use tenant-owned API credentials for PBX-side actions',
                ],
            },
            {
                'heading': 'Finish with reports, quotas and roles',
                'text': (
                    'A good 3CX setup is not finished when data arrives. Zentryc completes the '
                    'operational layer with user roles, scheduled reports, billing rates, quota '
                    'plans and supervisor wallboards.'
                ),
                'bullets': [
                    'Create role-based access for admins, supervisors and read-only users',
                    'Schedule CSV, Excel, PDF or HTML reports',
                    'Configure billing rules and quota plans before go-live',
                ],
            },
        ],
        'faq': [
            {
                'question': 'What do I need before connecting 3CX to Zentryc?',
                'answer': 'You need the 3CX call feed details, the tenant company setup in Zentryc and, for advanced queue metrics or call control, 3CX XAPI credentials.',
            },
            {
                'question': 'Can Zentryc sync 3CX extensions?',
                'answer': 'Yes. The platform includes 3CX user and extension sync so administrators can keep extension names, emails, registration state and PBX user IDs aligned.',
            },
            {
                'question': 'Does setup include billing and quotas?',
                'answer': 'Yes. Zentryc setup can include call patterns, rates, quota plans, per-extension balances and billing reports.',
            },
        ],
    },
    '3cx-call-control': {
        'slug': '3cx-call-control',
        'title': '3CX Call Control & External Call Blocking Software | Zentryc',
        'meta_description': (
            'Manage 3CX call control with external-call blocking, quota enforcement, '
            'extension permissions and tenant-owned 3CX API actions.'
        ),
        'meta_keywords': (
            '3CX call control, 3CX external call blocking, 3CX call permission, 3CX API control, '
            '3CX extension blocking, 3CX outbound call control, PBX call control'
        ),
        'og_title': '3CX Call Control and External Call Blocking',
        'og_description': 'Control extension external calling from quota status, admin action and tenant-owned 3CX API credentials.',
        'eyebrow': '3CX Call Control',
        'headline': 'Turn 3CX call permissions into an operational control point',
        'subhead': (
            'Zentryc connects billing logic, quota status and PBX-side call permissions so '
            'administrators can control external calling by extension without losing visibility '
            'into why a change happened.'
        ),
        'screenshot': 'images/solutions/real-3cx-call-control.jpg',
        'screenshot_alt': 'Authenticated Zentryc quota control view showing total extensions, exhausted balances and external-call blocked status.',
        'primary_keyword': '3CX Call Control',
        'supporting_keywords': [
            '3CX external call blocking',
            '3CX extension blocking',
            '3CX API control',
            '3CX outbound call control',
            'PBX call permission management',
        ],
        'snippet': {
            'title': 'External Calling Control',
            'metrics': [
                {'label': 'Allowed', 'value': '272', 'tone': 'ok'},
                {'label': 'Blocked', 'value': '6', 'tone': 'danger'},
                {'label': 'Pending review', 'value': '8', 'tone': 'warn'},
            ],
            'rows': [
                {'label': 'Ext 146', 'value': 'Blocked by quota', 'tone': 'danger'},
                {'label': 'Ext 204', 'value': 'Allowed after top-up', 'tone': 'ok'},
                {'label': 'Ext 315', 'value': 'Admin review', 'tone': 'warn'},
            ],
        },
        'proof_points': [
            'Admin toggle for allow or block external calling',
            'Quota-driven control when balance is exhausted',
            'Tenant-specific PBX URL, user and password fields',
            '3CX XAPI lookup by extension number and user ID',
            'Idempotent background enforcement task',
        ],
        'sections': [
            {
                'heading': 'Control 3CX external calling from the portal',
                'text': (
                    'Supervisors and company administrators need more than after-the-fact call '
                    'reports. Zentryc gives them a practical control layer for external calling '
                    'without asking every team to sign into the PBX console.'
                ),
                'bullets': [
                    'Allow or block external calling per extension',
                    'Show blocked status next to quota and usage data',
                    'Keep PBX actions scoped to the owning tenant company',
                ],
            },
            {
                'heading': 'Use call control as part of billing governance',
                'text': (
                    'External-call permissions become more useful when they are tied to spend. '
                    'Zentryc can move an extension from allowed to blocked when the quota is '
                    'exhausted, then return it after the balance is replenished.'
                ),
                'bullets': [
                    'Detect exhausted balances after CDR cost calculation',
                    'Run PBX enforcement asynchronously so ingestion stays fast',
                    'Avoid repeated PBX calls when the state has not changed',
                ],
            },
            {
                'heading': 'Built for multi-tenant PBX administration',
                'text': (
                    'Each company stores its own 3CX API endpoint and credentials. That keeps '
                    '3CX call control aligned with tenant isolation, role access and audit needs.'
                ),
                'bullets': [
                    'No hardcoded shared PBX credentials in the call-control module',
                    'Company admins can only act on their own extensions',
                    'Use the same extension directory that powers reporting and billing',
                ],
            },
        ],
        'faq': [
            {
                'question': 'Can non-PBX administrators manage external-call blocking?',
                'answer': 'Yes. Zentryc exposes controlled extension actions to authorized company administrators while keeping the actual 3CX API credentials tenant-owned and server-side.',
            },
            {
                'question': 'Is call control tied to billing quota?',
                'answer': 'It can be. When quota enforcement is enabled, exhausted extension balances can trigger 3CX external-call blocking automatically.',
            },
            {
                'question': 'Does Zentryc call the PBX on every CDR?',
                'answer': 'No. Quota enforcement is designed to act on state transitions, so the PBX update runs only when an extension needs to move between allowed and blocked states.',
            },
        ],
    },
    'call-center-setup-evaluation': {
        'slug': 'call-center-setup-evaluation',
        'title': 'Call Center Setup & Evaluation Software for 3CX ACD KPIs | Zentryc',
        'meta_description': (
            'Call center setup and evaluation for 3CX with real ACD KPIs, queue '
            'performance, agent productivity, abandonment, CSAT and reports.'
        ),
        'meta_keywords': (
            'call center setup, call center evaluation, call center KPI software, 3CX call center setup, '
            'agent evaluation, queue performance, ACD analytics, call center reporting'
        ),
        'og_title': 'Call Center Setup and Evaluation for 3CX Teams',
        'og_description': 'Measure queues, agents, service level, abandonment and customer feedback from one Zentryc dashboard.',
        'eyebrow': 'Call Center Setup & Evaluation',
        'headline': 'Evaluate your call center with metrics supervisors can trust',
        'subhead': (
            'Zentryc helps 3CX call centers move from basic call logs to real evaluation: '
            'queue service level, ASA, abandon rate, agent productivity, missed-call patterns, '
            'wallboards, reports and post-call survey results.'
        ),
        'screenshot': 'images/solutions/real-call-center-evaluation.jpg',
        'screenshot_alt': 'Authenticated Zentryc call-center dashboard with IVR calls, answered calls, missed calls, average talk time, ASA and abandonment KPIs.',
        'primary_keyword': 'Call Center Evaluation',
        'supporting_keywords': [
            'call center setup',
            '3CX call center setup',
            'agent evaluation',
            'queue performance',
            'ACD analytics',
        ],
        'snippet': {
            'title': 'Supervisor Evaluation View',
            'metrics': [
                {'label': 'Answer rate', 'value': '92%', 'tone': 'ok'},
                {'label': 'ASA', 'value': '0:18', 'tone': 'info'},
                {'label': 'Abandon', 'value': '4.8%', 'tone': 'warn'},
            ],
            'rows': [
                {'label': 'Sales Queue', 'value': 'Above SLA', 'tone': 'ok'},
                {'label': 'Support Queue', 'value': 'Longest wait 1:24', 'tone': 'warn'},
                {'label': 'Agent team', 'value': '18 live', 'tone': 'info'},
            ],
        },
        'proof_points': [
            'Real ACD queue KPIs from 3CX detailed queue statistics',
            'Agent productivity with answered, lost, AHT and occupancy metrics',
            'Missed calls, abandoned calls and callback tracking',
            'Live wallboard for calls waiting and longest wait',
            'Scheduled reports and post-call survey analytics',
        ],
        'sections': [
            {
                'heading': 'Set up the call center around measurable queues',
                'text': (
                    'A call-center setup should define queues, agents, service targets and '
                    'supervisor ownership before the first report is sent. Zentryc models those '
                    'entities so performance is measured at the right operational level.'
                ),
                'bullets': [
                    'Map 3CX queues and agents into a vendor-neutral ACD model',
                    'Define service-level targets, short-abandon thresholds and teams',
                    'Track daily rollups so longer date ranges stay fast',
                ],
            },
            {
                'heading': 'Evaluate agents without misleading IVR numbers',
                'text': (
                    'Basic PBX reports often treat IVR auto-answer as a successful call. Zentryc '
                    'focuses on queue and agent timing so supervisors can evaluate the real customer '
                    'experience: waiting, ringing, answering, abandoning and talking.'
                ),
                'bullets': [
                    'Answer rate, ASA, AHT, occupancy and lost-ring visibility',
                    'Per-queue and per-agent drill-downs',
                    'Callback and missed-call tracking for follow-up accountability',
                ],
            },
            {
                'heading': 'Close the loop with surveys and scheduled reports',
                'text': (
                    'Evaluation is stronger when operational KPIs and customer feedback live together. '
                    'Zentryc supports post-call survey ingestion, CSAT metrics and scheduled reporting '
                    'for managers who need consistent evidence.'
                ),
                'bullets': [
                    '3CX Call Flow Designer survey guide and ingest API',
                    'CSV, Excel, PDF and HTML report delivery',
                    'Supervisor wallboards for live management during the day',
                ],
            },
        ],
        'faq': [
            {
                'question': 'What makes Zentryc different from basic 3CX call reports?',
                'answer': 'Zentryc focuses on queue and agent timing, not only IVR auto-answer events, so service level, ASA and abandonment reflect the real customer wait experience.',
            },
            {
                'question': 'Can supervisors evaluate individual agents?',
                'answer': 'Yes. Zentryc includes per-agent productivity views such as answered calls, lost rings, answer rate, AHT and occupancy where the source data is available.',
            },
            {
                'question': 'Can we include customer satisfaction in call center evaluation?',
                'answer': 'Yes. Zentryc includes post-call survey ingestion and reporting so teams can combine operational KPIs with CSAT or survey responses.',
            },
        ],
    },
    'cisco-ip-telephony-billing': {
        'slug': 'cisco-ip-telephony-billing',
        'title': 'Cisco IP Telephony Billing & CUCM CDR Analytics | Zentryc',
        'meta_description': (
            'Cisco IP Telephony billing for CUCM CDR/CMR files: call accounting, '
            'rated usage, chargeback, MOS, jitter, packet loss and latency.'
        ),
        'meta_keywords': (
            'CISCO IP Telephony billing, Cisco IP Telephony billing, CUCM CDR billing, Cisco call accounting, '
            'Cisco CDR analytics, CUCM call detail records, Cisco CMR, IP telephony billing'
        ),
        'og_title': 'Cisco IP Telephony Billing and CUCM CDR Analytics',
        'og_description': 'Normalize CUCM CDR and CMR files into rated call accounting, billing and quality analytics.',
        'eyebrow': 'Cisco IP Telephony Billing',
        'headline': 'Bring Cisco CUCM call accounting into the same billing portal',
        'subhead': (
            'Zentryc is built on a vendor-neutral call model, so Cisco CUCM CDR and CMR '
            'files can be normalized for call accounting, rated billing, chargeback reports '
            'and voice-quality analytics alongside 3CX and other PBX platforms.'
        ),
        'screenshot': 'images/solutions/real-cisco-ip-telephony-billing.jpg',
        'screenshot_alt': 'Authenticated Zentryc call details view with all calls, incoming, outgoing, local and international billing filters.',
        'primary_keyword': 'Cisco IP Telephony Billing',
        'supporting_keywords': [
            'CUCM CDR billing',
            'Cisco call accounting',
            'Cisco CDR analytics',
            'Cisco CMR reporting',
            'IP telephony billing',
        ],
        'snippet': {
            'title': 'CUCM Billing & Quality View',
            'metrics': [
                {'label': 'Rated calls', 'value': '1.8M', 'tone': 'info'},
                {'label': 'Avg MOS', 'value': '4.32', 'tone': 'ok'},
                {'label': 'Loss alerts', 'value': '11', 'tone': 'warn'},
            ],
            'rows': [
                {'label': 'HQ CUCM', 'value': 'CDR/CMR imported', 'tone': 'ok'},
                {'label': 'International', 'value': 'Rated by prefix', 'tone': 'info'},
                {'label': 'Branch 07', 'value': 'Packet loss review', 'tone': 'warn'},
            ],
        },
        'proof_points': [
            'CUCM CDR row parsing into canonical call records',
            'CMR quality metrics for MOS, jitter, latency and packet loss',
            'Call rating and chargeback reporting by extension or tenant',
            'Multi-currency and tax-ready billing model',
            'Vendor-neutral source field for Cisco, 3CX, Teams, Webex, Zoom and more',
        ],
        'sections': [
            {
                'heading': 'Normalize CUCM CDR files for billing',
                'text': (
                    'Cisco CUCM environments usually produce file-based CDR and CMR exports. '
                    'Zentryc maps those records into a canonical billing model with caller, callee, '
                    'duration, correlation ID and source PBX preserved for reporting.'
                ),
                'bullets': [
                    'Use CUCM global call ID fields for stable external and correlation IDs',
                    'Rate calls after normalization using the same billing rules as other PBXs',
                    'Report by tenant, extension, branch, call type or country pattern',
                ],
            },
            {
                'heading': 'Add voice-quality context from CMR',
                'text': (
                    'Billing teams care about cost, but telecom teams also need quality. Zentryc '
                    'can join CUCM CMR fields such as MOS, jitter, latency and packet loss onto '
                    'the rated call record for operational troubleshooting.'
                ),
                'bullets': [
                    'Store MOS values where CUCM exports them',
                    'Calculate packet-loss percentage from lost and received packet counts',
                    'Keep quality metrics next to call cost and duration',
                ],
            },
            {
                'heading': 'Unify Cisco and 3CX billing operations',
                'text': (
                    'Many enterprises operate more than one PBX family. Zentryc is designed so '
                    'Cisco CUCM, 3CX and cloud telephony data can flow into one reporting, billing '
                    'and analytics experience.'
                ),
                'bullets': [
                    'Use one chargeback and invoice workflow across PBX sources',
                    'Compare cost and quality across branches or platforms',
                    'Prepare for multi-vendor migrations without losing reporting history',
                ],
            },
        ],
        'faq': [
            {
                'question': 'Does Zentryc support Cisco CUCM CDR files?',
                'answer': 'The codebase includes a CUCM CDR and CMR adapter that normalizes Cisco rows into the canonical Zentryc call record shape for billing and analytics workflows.',
            },
            {
                'question': 'Can Cisco CMR quality metrics be reported?',
                'answer': 'Yes. Zentryc maps MOS, jitter, latency and packet-loss fields where the CUCM CMR export provides them.',
            },
            {
                'question': 'Can Cisco and 3CX billing live in one portal?',
                'answer': 'Yes. Zentryc uses a vendor-neutral call record model so Cisco CUCM and 3CX data can support one billing and reporting experience.',
            },
        ],
    },
}

SOLUTION_PAGE_LIST = list(SOLUTION_PAGES.values())

PUBLIC_PATHS = [
    '/', '/features/', '/pricing/', '/about/', '/contact/',
    *[f'/solutions/{slug}/' for slug in SOLUTION_PAGES],
    '/kb/', '/kb/3cx-post-call-survey/',
]

KB_ARTICLES = [
    {
        'slug': '3cx-post-call-survey',
        'title': '3CX Post-Call Survey (CFD) — Setup Guide',
        'subtitle': 'Connect 3CX Call Flow Designer surveys to Zentryc for CSAT, dashboards and automated reporting.',
        'category': '3CX Integration',
        'read_minutes': 12,
        'hero_image': 'images/kb/survey-dashboard-hero.png',
        'og_image': 'images/kb/survey-settings.png',
        'keywords': (
            '3CX post-call survey, 3CX CFD survey, Call Flow Designer CSAT, '
            'Zentryc survey integration, customer satisfaction 3CX, queue survey, '
            'X-Survey-Token, survey ingest API'
        ),
        'description': (
            'Step-by-step guide to enable Zentryc post-call surveys: portal settings, '
            '3CX Call Flow Designer (CFD) Survey component, HTTP ingest API, queue '
            'triggers, verification and troubleshooting.'
        ),
        'template': 'public/kb/3cx-post-call-survey.html',
    },
]


def home(request):
    return render(request, 'public/home.html', {'solutions': SOLUTION_PAGE_LIST})


def features(request):
    return render(request, 'public/features.html')


def pricing(request):
    return render(request, 'public/pricing.html')


def about(request):
    return render(request, 'public/about.html')


def solution_page(request, slug):
    page = SOLUTION_PAGES.get(slug)
    if not page:
        from django.http import Http404
        raise Http404('Solution page not found')
    related = [p for p in SOLUTION_PAGE_LIST if p['slug'] != slug]
    return render(request, 'public/solution.html', {'page': page, 'related': related})


def kb_index(request):
    return render(request, 'public/kb_index.html', {'articles': KB_ARTICLES})


def kb_article(request, slug):
    article = next((a for a in KB_ARTICLES if a['slug'] == slug), None)
    if not article:
        from django.http import Http404
        raise Http404('Article not found')
    return render(request, article['template'], {'article': article, 'articles': KB_ARTICLES})


def contact(request):
    sent = False
    inquiry_type = 'pricing'
    if request.method == 'POST':
        data = {k: (request.POST.get(k) or '').strip()
                for k in ('name', 'email', 'company', 'message', 'inquiry_type')}
        inquiry_type = data.get('inquiry_type') or 'pricing'
        recipient = PRICING_EMAIL if inquiry_type == 'pricing' else SUPPORT_EMAIL
        inquiry_label = 'Pricing / demo' if inquiry_type == 'pricing' else 'Support / general'
        # Best-effort lead notification; never block the thank-you on SMTP.
        try:
            from django.conf import settings
            from django.core.mail import send_mail
            body = (f"New Zentryc {inquiry_label.lower()} request\n\n"
                    f"Inquiry type: {inquiry_label}\n"
                    f"Name: {data['name']}\nEmail: {data['email']}\n"
                    f"Company: {data['company']}\n\n{data['message']}")
            send_mail(f'Zentryc {inquiry_label} request', body,
                      settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=True)
        except Exception as e:
            logger.warning('contact form email failed: %s', e)
        logger.info('contact lead: %s <%s> (%s) type=%s recipient=%s',
                    data['name'], data['email'], data['company'], inquiry_type, recipient)
        sent = True
    return render(request, 'public/contact.html', {
        'sent': sent,
        'inquiry_type': inquiry_type,
        'pricing_email': PRICING_EMAIL,
        'support_email': SUPPORT_EMAIL,
    })


@require_safe
def robots_txt(request):
    lines = [
        'User-agent: *',
        'Allow: /',
        'Disallow: /accounts/',
        'Disallow: /admin/',
        'Disallow: /call-center/',
        'Disallow: /billing/',
        f'Sitemap: {SITE}/sitemap.xml',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain')


@require_safe
def sitemap_xml(request):
    today = ''
    try:
        from django.utils import timezone
        today = timezone.localdate().isoformat()
    except Exception:
        pass
    urls = []
    for path in PUBLIC_PATHS:
        if path == '/':
            prio = '1.0'
        elif path.startswith('/solutions/'):
            prio = '0.9'
        elif path.startswith('/kb/'):
            prio = '0.85'
        else:
            prio = '0.8'
        urls.append(
            f'  <url><loc>{SITE}{path}</loc>'
            f'{"<lastmod>" + today + "</lastmod>" if today else ""}'
            f'<changefreq>weekly</changefreq><priority>{prio}</priority></url>')
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + '\n'.join(urls) + '\n</urlset>')
    return HttpResponse(xml, content_type='application/xml')
