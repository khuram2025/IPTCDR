from django.http import HttpResponse
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.colors import HexColor
from io import BytesIO
from .utils import get_date_range
from .models import CallRecord
from django.db.models import Q, Sum, Count
from datetime import timedelta
from django.utils import timezone
from django.db.models.functions import Length

def export_international_calls_excel(request):
    start_date, end_date, time_period, custom_date_range = get_date_range(request)

    call_records = CallRecord.objects.filter(
        Q(callee__regex=r'^\+[^9]') | 
        Q(callee__regex=r'^\+9[0-8]') | 
        Q(callee__regex=r'^00[^9]') | 
        Q(callee__regex=r'^009[0-8]'),
        call_time__range=[start_date, end_date]
    ).exclude(
        Q(callee__startswith='+966') | Q(callee__startswith='00966')
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "International Calls"

    headers = ['Date Time', 'Caller Name', 'Extension', 'Called Number', 'Duration', 'Country']
    ws.append(headers)

    for record in call_records:
        duration_str = str(timedelta(seconds=record.duration)) if record.duration is not None else "N/A"
        ws.append([
            record.call_time.strftime("%d %b, %Y %H:%M:%S"),
            record.from_dispname,
            record.caller,
            record.callee,
            duration_str,
            record.country
        ])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=international_calls.xlsx'
    wb.save(response)
    return response

def export_international_calls_pdf(request):
    start_date, end_date, time_period, custom_date_range = get_date_range(request)

    call_records = CallRecord.objects.filter(
        Q(callee__regex=r'^\+[^9]') | 
        Q(callee__regex=r'^\+9[0-8]') | 
        Q(callee__regex=r'^00[^9]') | 
        Q(callee__regex=r'^009[0-8]'),
        call_time__range=[start_date, end_date],
        duration__isnull=False
    ).exclude(
        Q(callee__startswith='+966') | Q(callee__startswith='00966')
    )

    # Calculate summary data
    summary = call_records.aggregate(
        total_calls=Count('id'),
        total_duration=Sum('duration'),
        total_cost=Sum('total_cost')
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch, leftMargin=0.5*inch, rightMargin=0.5*inch)
    elements = []

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=20, spaceAfter=12)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Heading2'], alignment=TA_CENTER, fontSize=14, spaceAfter=12, textColor=HexColor('#4a4a4a'))
    card_style = ParagraphStyle('Card', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER)

    # Color scheme
    primary_color = HexColor('#1c4587')
    secondary_color = HexColor('#cfe2f3')
    accent_color = HexColor('#f9cb9c')

    # Title and Subtitle
    elements.append(Paragraph("SMASCO International Call Record", title_style))
    
    if time_period == 'custom':
        date_range = f"{start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}"
    else:
        date_range = f"Last {time_period}"
    elements.append(Paragraph(f"Call Records for {date_range}", subtitle_style))

    elements.append(Spacer(1, 0.25*inch))

    # Summary Cards
    card_data = [
        ["Total Calls", "Total Duration", "Total Cost"],
        [f"{summary['total_calls']}", f"{timedelta(seconds=summary['total_duration'] or 0)}", f"{summary['total_cost']:.2f} SAR"]
    ]
    card_table = Table(card_data, colWidths=[2*inch]*3)
    card_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 1, primary_color),
        ('GRID', (0, 0), (-1, -1), 0.5, primary_color),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 1), (-1, -1), secondary_color),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
    ]))
    elements.append(card_table)
    elements.append(Spacer(1, 0.5*inch))

    # Call Details Table
    data = [['Date Time', 'Caller Name', 'Extension', 'Called Number', 'Duration', 'Country', 'Cost']]
    for record in call_records:
        data.append([
            record.call_time.strftime("%d %b, %Y %H:%M:%S"),
            record.from_dispname,
            record.caller,
            record.callee,
            str(timedelta(seconds=record.duration)),
            record.country,
            f"{record.total_cost:.2f} SAR"
        ])

    table = Table(data, colWidths=[1.2*inch, 1.2*inch, 0.8*inch, 1.2*inch, 0.8*inch, 0.8*inch, 0.8*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, primary_color),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, secondary_color])
    ]))
    elements.append(table)

    # Footer
    elements.append(Spacer(1, 0.5*inch))
    footer_text = f"Report generated on {timezone.now().strftime('%B %d, %Y at %I:%M %p')}"
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.gray, alignment=TA_RIGHT)
    elements.append(Paragraph(footer_text, footer_style))

    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=international_calls.pdf'
    response.write(buffer.getvalue())
    buffer.close()
    return response

def export_caller_calls_pdf(request, caller_number):
    search_query = request.GET.get('search', '')
    date_filter = request.GET.get('date_filter', '1M')
    custom_date_range = request.GET.get('custom_date', '')
    call_type = request.GET.get('call_type', 'all')

    start_date, end_date, time_period, custom_date_range = get_date_range(request)

    call_records = CallRecord.objects.filter(caller=caller_number, call_time__range=[start_date, end_date])

    if call_type == 'local':
        call_records = call_records.annotate(callee_length=Length('callee')).filter(
            callee_length__gt=4
        ).exclude(
            (Q(callee__startswith='+') | Q(callee__startswith='00')) & 
            ~(Q(callee__startswith='+966') | Q(callee__startswith='00966')) & 
            Q(callee_length__gt=11)
        )
    elif call_type == 'international':
        call_records = call_records.annotate(callee_length=Length('callee')).filter(
            (Q(callee__startswith='+') | Q(callee__startswith='00')) & 
            ~(Q(callee__startswith='+966') | Q(callee__startswith='00966')) & 
            Q(callee_length__gt=11)
        )
    elif call_type == 'incoming':
        call_records = call_records.filter(from_type="Line")

    if search_query:
        call_records = call_records.filter(Q(callee__icontains=search_query) | Q(call_time__icontains=search_query))

    # Calculate summary data
    summary = call_records.aggregate(
        total_calls=Count('id'),
        total_duration=Sum('duration'),
        total_cost=Sum('total_cost')
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch, leftMargin=0.5*inch, rightMargin=0.5*inch)
    elements = []

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=20, spaceAfter=12)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Heading2'], alignment=TA_CENTER, fontSize=14, spaceAfter=12, textColor=HexColor('#4a4a4a'))
    card_style = ParagraphStyle('Card', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER)

    # Color scheme
    primary_color = HexColor('#1c4587')
    secondary_color = HexColor('#cfe2f3')
    accent_color = HexColor('#f9cb9c')

    # Title and Subtitle
    elements.append(Paragraph(f"SMASCO Call Record for {caller_number}", title_style))
    
    if time_period == 'custom':
        date_range = f"{start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}"
    else:
        date_range = f"Last {time_period}"
    
    call_type_text = {
        'all': 'All Calls',
        'local': 'Local Calls',
        'international': 'International Calls',
        'incoming': 'Incoming Calls'
    }.get(call_type, 'All Calls')

    elements.append(Paragraph(f"{call_type_text} for {date_range}", subtitle_style))

    elements.append(Spacer(1, 0.25*inch))

    # Summary Cards
    card_data = [
        ["Total Calls", "Total Duration", "Total Cost"],
        [f"{summary['total_calls']}", f"{timedelta(seconds=summary['total_duration'] or 0)}", f"{summary['total_cost']:.2f} SAR"]
    ]
    card_table = Table(card_data, colWidths=[2*inch]*3)
    card_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 1, primary_color),
        ('GRID', (0, 0), (-1, -1), 0.5, primary_color),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 1), (-1, -1), secondary_color),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
    ]))
    elements.append(card_table)
    elements.append(Spacer(1, 0.5*inch))

    # Call Details Table
    data = [['Date Time', 'Caller Name', 'Extension', 'Called Number', 'Duration', 'Call Type', 'Cost']]
    for record in call_records:
        data.append([
            record.call_time.strftime("%d %b, %Y %H:%M:%S"),
            record.from_dispname,
            record.caller,
            record.callee,
            str(timedelta(seconds=record.duration)),
            record.to_type,
            f"{record.total_cost:.2f} SAR"
        ])

    table = Table(data, colWidths=[1.2*inch, 1.2*inch, 0.8*inch, 1.2*inch, 0.8*inch, 0.8*inch, 0.8*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, primary_color),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, secondary_color])
    ]))
    elements.append(table)

    # Footer
    elements.append(Spacer(1, 0.5*inch))
    footer_text = f"Report generated on {timezone.now().strftime('%B %d, %Y at %I:%M %p')}"
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.gray, alignment=TA_RIGHT)
    elements.append(Paragraph(footer_text, footer_style))

    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=calls_for_{caller_number}.pdf'
    response.write(buffer.getvalue())
    buffer.close()
    return response