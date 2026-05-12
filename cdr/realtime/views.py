"""HTML views for the live wallboard."""
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.safestring import mark_safe

from .snapshot import build, build_heatmap


def _render_wallboard(request, template):
    company = getattr(request.user, 'company', None)
    snapshot = build(company)
    # Pass as a JSON literal so the template can drop it into a JS variable.
    return render(request, template, {
        'snapshot_json': mark_safe(json.dumps(snapshot, default=str)),
    })


@login_required
def wallboard(request):
    """Standard wallboard inside the admin sidebar layout."""
    return _render_wallboard(request, 'realtime/wallboard.html')


@login_required
def wallboard_projection(request):
    """Full-screen, dark-theme view for TVs in call-center floors."""
    return _render_wallboard(request, 'realtime/wallboard_projection.html')


@login_required
def heatmap_data(request):
    """JSON endpoint for the heatmap widget (refreshable from JS)."""
    company = getattr(request.user, 'company', None)
    days = int(request.GET.get('days', 7))
    return JsonResponse(build_heatmap(company, days=days))


@login_required
def heatmap_view(request):
    """Standalone page rendering the call-volume heatmap."""
    company = getattr(request.user, 'company', None)
    return render(request, 'realtime/heatmap.html', {
        'heatmap': build_heatmap(company),
    })
