"""
DEMO / SYNTHETIC DATA
Industrial Hydraulic Pump HP-4000 — Demo Technical Datasheet
This document contains synthetic specifications for demonstration purposes only.
NOT real manufacturer data. Created for IPTE hackathon demo.
"""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT

def create_demo_pdf(output_path: str):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'Title', parent=styles['Title'],
        fontSize=18, spaceAfter=6, textColor=colors.HexColor('#1a1a2e')
    )
    h1_style = ParagraphStyle(
        'H1', parent=styles['Heading1'],
        fontSize=14, spaceAfter=4, spaceBefore=12, textColor=colors.HexColor('#16213e')
    )
    h2_style = ParagraphStyle(
        'H2', parent=styles['Heading2'],
        fontSize=11, spaceAfter=3, spaceBefore=8, textColor=colors.HexColor('#0f3460')
    )
    body_style = ParagraphStyle(
        'Body', parent=styles['Normal'],
        fontSize=9, spaceAfter=3
    )
    note_style = ParagraphStyle(
        'Note', parent=styles['Normal'],
        fontSize=8, textColor=colors.HexColor('#cc0000'), spaceAfter=6, borderPad=4
    )

    story = []

    # Page 1: Header + Overview
    story.append(Paragraph("⚠ DEMO / SYNTHETIC DATA — NOT REAL MANUFACTURER SPECIFICATIONS", note_style))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("Technical Data Sheet", styles['Heading2']))
    story.append(Paragraph("Industrial Hydraulic Pump — Model HP-4000", title_style))
    story.append(Paragraph("HydroDyn Pumps Pvt. Ltd.", styles['Heading3']))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#0f3460')))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph("1. Product Overview", h1_style))
    story.append(Paragraph(
        "The HP-4000 is a high-performance industrial hydraulic pump designed for demanding "
        "fluid power applications. It delivers reliable, continuous-duty performance in "
        "manufacturing, mining, and heavy machinery installations. "
        "Model number: HP-4000. SKU: HDPUMP-4000-230V.",
        body_style
    ))
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("2. Electrical Specifications", h1_style))
    story.append(Paragraph(
        "The HP-4000 operates on a standard three-phase industrial supply. "
        "Rated voltage: 230 V (±10%). Rated current: 16 A. Frequency: 50 Hz. "
        "Power factor: 0.87. The motor is IE3 efficiency class compliant.",
        body_style
    ))
    story.append(Spacer(1, 2*mm))

    story.append(Paragraph("3. Performance Specifications", h1_style))
    story.append(Paragraph(
        "Rated power output: 5 HP (3.73 kW). Maximum operating pressure: 250 bar (3,626 psi). "
        "Nominal flow rate: 45 L/min at rated speed. "
        "Pump speed: 1450 RPM at 50 Hz. "
        "Volumetric efficiency: ≥ 92% at rated conditions.",
        body_style
    ))
    story.append(Spacer(1, 2*mm))

    story.append(Paragraph("4. Physical Specifications", h1_style))
    story.append(Paragraph(
        "Net weight: 38 kg (83.8 lb). "
        "Overall dimensions (L × W × H): 580 mm × 280 mm × 320 mm. "
        "Fluid port connections: SAE flange, 1-inch BSP. "
        "Mounting: Four-bolt flange mount, B3/B5 IEC.",
        body_style
    ))
    story.append(Spacer(1, 2*mm))

    story.append(Paragraph("5. Operating Conditions", h1_style))
    story.append(Paragraph(
        "Operating temperature range: −10 °C to +70 °C. "
        "Storage temperature: −20 °C to +85 °C. "
        "Recommended hydraulic fluid: ISO VG 46 mineral oil. "
        "Filtration: 25 µm nominal. "
        "Protection class: IP55.",
        body_style
    ))

    # Page break content (page 2)
    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("6. Consolidated Specifications Table", h1_style))

    table_data = [
        ['Parameter', 'Value', 'Unit', 'Notes'],
        ['Rated Voltage', '230', 'V', '±10%, 3-phase'],
        ['Rated Current', '16', 'A', 'Full load'],
        ['Rated Power', '5 HP / 3.73 kW', 'HP / kW', 'IE3 motor'],
        ['Max Pressure', '250', 'bar', '3,626 psi equivalent'],
        ['Flow Rate', '45', 'L/min', 'At rated speed'],
        ['Pump Speed', '1450', 'RPM', '50 Hz supply'],
        ['Net Weight', '38', 'kg', '83.8 lb equivalent'],
        ['Length', '580', 'mm', '22.8 inch'],
        ['Width', '280', 'mm', '11.0 inch'],
        ['Height', '320', 'mm', '12.6 inch'],
        ['Min Operating Temp', '-10', '°C', '14 °F'],
        ['Max Operating Temp', '70', '°C', '158 °F'],
        ['Protection Class', 'IP55', '—', 'IEC 60529'],
    ]

    tbl = Table(table_data, colWidths=[48*mm, 35*mm, 22*mm, 52*mm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f3460')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4f8')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph("7. Certifications & Compliance", h1_style))
    story.append(Paragraph(
        "CE Marked — EU Machinery Directive 2006/42/EC. "
        "ISO 4413 — Hydraulic fluid power safety requirements. "
        "IEC 60034-30-1 — IE3 motor efficiency class. "
        "RoHS compliant. "
        "Country of origin: India.",
        body_style
    ))
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("8. Application Range", h1_style))
    story.append(Paragraph(
        "Suitable for: industrial presses, CNC machine tools, injection moulding machines, "
        "test rigs, and automated manufacturing equipment. "
        "Not suitable for: explosive atmospheres (ATEX-rated versions available on request), "
        "water-glycol fluids without special seals, or continuous operation above 70 °C.",
        body_style
    ))
    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "⚠ DEMO / SYNTHETIC DATA — For IPTE hackathon demonstration only. "
        "Specifications are representative but not sourced from a real product.",
        note_style
    ))

    doc.build(story)
    print(f"[DEMO PDF CREATED] {output_path}")

if __name__ == "__main__":
    import os
    os.makedirs("demo/hydraulic_pump", exist_ok=True)
    create_demo_pdf("demo/hydraulic_pump/hp4000_datasheet.pdf")
