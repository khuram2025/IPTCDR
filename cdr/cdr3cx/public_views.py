"""Public marketing site (SEO-optimised, no auth) for connect.zentryc.com."""
import logging

from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)

SITE = 'https://connect.zentryc.com'
PUBLIC_PATHS = [
    '/', '/features/', '/pricing/', '/about/', '/contact/',
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
    return render(request, 'public/home.html')


def features(request):
    return render(request, 'public/features.html')


def pricing(request):
    return render(request, 'public/pricing.html')


def about(request):
    return render(request, 'public/about.html')


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
    if request.method == 'POST':
        data = {k: (request.POST.get(k) or '').strip()
                for k in ('name', 'email', 'company', 'message')}
        # Best-effort lead notification; never block the thank-you on SMTP.
        try:
            from django.conf import settings
            from django.core.mail import send_mail
            body = ("New Zentryc demo request\n\n"
                    f"Name: {data['name']}\nEmail: {data['email']}\n"
                    f"Company: {data['company']}\n\n{data['message']}")
            send_mail('Zentryc demo request', body, settings.DEFAULT_FROM_EMAIL,
                      [getattr(settings, 'QUOTA_ALERT_FALLBACK_EMAIL', settings.DEFAULT_FROM_EMAIL)],
                      fail_silently=True)
        except Exception as e:
            logger.warning('contact form email failed: %s', e)
        logger.info('contact lead: %s <%s> (%s)', data['name'], data['email'], data['company'])
        sent = True
    return render(request, 'public/contact.html', {'sent': sent})


@require_GET
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


@require_GET
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
