import os
import docx
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

def set_run_font(run, font_name="Century Gothic", size_pt=10, bold=False, italic=False, color_rgb=None):
    run.font.name = font_name
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.italic = italic
    if color_rgb:
        run.font.color.rgb = color_rgb
    rPr = run._r.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:ascii'), font_name)
    rFonts.set(qn('w:hAnsi'), font_name)
    rFonts.set(qn('w:cs'), font_name)

def set_cell_shading(cell, color_hex):
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def set_cell_margins(cell, top=80, bottom=80, left=100, right=100):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def clean_cell_first_paragraph(cell):
    p0 = cell.paragraphs[0]
    p0.text = ""
    for p in list(cell.paragraphs[1:]):
        p._p.getparent().remove(p._p)
    return p0

def populate_1_1():
    doc_path = "Reflexiones/1.1_APT122_AutoevaluacionCompetenciasFase1.docx"
    doc = docx.Document(doc_path)

    # -------------------------------------------------------------------------
    # 1. Update Table 1: Student Information
    # -------------------------------------------------------------------------
    t1 = doc.tables[1]
    
    # Row 0: Merged cell for Escuela
    c_esc = t1.rows[0].cells[0]
    p_esc = clean_cell_first_paragraph(c_esc)
    p_esc.paragraph_format.space_before = Pt(3)
    p_esc.paragraph_format.space_after = Pt(3)
    r_esc1 = p_esc.add_run("Escuela: ")
    set_run_font(r_esc1, font_name="Century Gothic", size_pt=10, bold=True, color_rgb=RGBColor(0, 51, 102))
    r_esc2 = p_esc.add_run("Escuela de Informática y Telecomunicaciones — Duoc UC")
    set_run_font(r_esc2, font_name="Century Gothic", size_pt=10, bold=False, color_rgb=RGBColor(30, 30, 30))
    set_cell_shading(c_esc, "F2F4F4")
    set_cell_margins(c_esc, 60, 60, 80, 80)

    # Rows 1, 2, 3
    fields = [
        ("Nombre completo", "Gabriel Ignacio Cárdenas Valdés"),
        ("Plan de Estudio", "Ingeniería en Informática"),
        ("Año de ingreso", "2023")
    ]
    for r_i, (k, v) in enumerate(fields, start=1):
        row = t1.rows[r_i]
        c0, c1 = row.cells[0], row.cells[1]
        
        p0 = clean_cell_first_paragraph(c0)
        p0.paragraph_format.space_before = Pt(2)
        p0.paragraph_format.space_after = Pt(2)
        r0 = p0.add_run(k)
        set_run_font(r0, font_name="Century Gothic", size_pt=9.5, bold=True, color_rgb=RGBColor(0, 51, 102))
        set_cell_shading(c0, "F2F4F4")
        set_cell_margins(c0, 50, 50, 80, 80)

        p1 = clean_cell_first_paragraph(c1)
        p1.paragraph_format.space_before = Pt(2)
        p1.paragraph_format.space_after = Pt(2)
        r1 = p1.add_run(v)
        set_run_font(r1, font_name="Century Gothic", size_pt=9.5, bold=False, color_rgb=RGBColor(30, 30, 30))
        set_cell_margins(c1, 50, 50, 80, 80)

    # -------------------------------------------------------------------------
    # 2. Update Table 2: Competency Assessment Matrix
    # -------------------------------------------------------------------------
    t2 = doc.tables[2]
    
    # 8 Competencies of the Graduate Profile (4 Disciplinary + 4 Employability)
    # Selected level: 1=ED, 2=AD, 3=DA, 4=DP, 5=DNL
    competencias_data = [
        # Competencia 1
        (
            "1. Desarrollo de Soluciones de Software de Alto Rendimiento",
            "Perfil de Egreso — Disciplinaria | Unidades: 4.1 Construye, 4.2 Integra, 4.3 Implanta componentes modulares.",
            1, # ED
            "Poseo un dominio avanzado en el diseño e implementación de arquitecturas de software modulares y desacopladas en Python (src/tsc), aplicando principios SOLID, patrones de diseño y estándares PEP 8. He integrado con éxito el simulador SUMO a través de libsumo y TraCI en Windows 11 nativo, wrappers PettingZoo/SuperSuit para entrenamiento de RL y controladores de tráfico clásicos y neuronales. El código está completamente documentado y estructurado para su mantenimiento y escalabilidad a largo plazo."
        ),
        # Competencia 2
        (
            "2. Construcción y Modelado de Datos Escalables",
            "Perfil de Egreso — Disciplinaria | Unidades: 3.1 Diseña y 3.2 Implementa modelos espaciales, temporales y relacionales.",
            1, # ED
            "Demuestro sólida capacidad para modelar redes urbanas complejas como grafos dirigidos formales G = (V, E) en PyTorch Geometric (GNNRouter), integrando vectores nodales dinámicos (densidades, colas y velocidades promedio) desde TraCI. Asimismo, he diseñado e implementado cuatro perfiles horarios formales de demanda vehicular (valle, punta mañana, punta tarde y sobresaturado) en esquemas XML (.rou.xml) y persistido telemetría masiva en estructuras JSON y CSV para análisis analítico."
        ),
        # Competencia 3
        (
            "3. Pruebas y Certificación de Calidad de Software",
            "Perfil de Egreso — Disciplinaria | Unidades: 1.1 Diseña pruebas, 1.2 Aplica pruebas de validación, 1.3 Desarrolla mejoras.",
            1, # ED
            "He diseñado y ejecutado una suite de 12 pruebas automatizadas con el framework pytest (tests/test_pipeline.py y tests/test_demand_and_network.py), alcanzando un 100% de aprobación continua (12/12 passed en 2.63s). Valido invariantes físicas de conmutación de semáforos, límites de ciclo de Webster y preservación de estados en TraCI. Además, desarrollé scripts/diagnose_net.py para verificar la sanidad de la red Alameda-Providencia, certificando 0 colisiones, 0 teletransportes y declarándola 'APTA'."
        ),
        # Competencia 4
        (
            "4. Gestión de Proyectos Informáticos y Toma de Decisiones",
            "Perfil de Egreso — Disciplinaria | Unidades: 2.1 Planifica proyectos, 2.2 Controla proyectos informáticos con mitigación de riesgos.",
            2, # AD
            "Planifico y controlo el proyecto de tesis bajo una metodología ágil iterativa organizada en 4 fases temporales con entregables verificables y control estricto de versiones en Git. Evalúo alternativas técnicas rigurosamente (como la selección de SUMO frente a otros simuladores y la adopción de Windows 11 nativo sobre WSL2). Marco 'Alto Dominio' reconociendo que debo reforzar la gestión predictiva formal de contingencias frente a la alta incertidumbre en proyectos de I+D avanzada y el escalado distribuido en clusters."
        ),
        # Competencia 5
        (
            "5. Innovación, Pensamiento Crítico y Resolución de Problemas",
            "Sello Institucional Duoc UC — Empleabilidad | Pensamiento analítico e investigación científica autónoma.",
            1, # ED
            "Cuento con una alta capacidad de análisis y autonomía para investigar literatura científica de frontera (papers de IEEE, ACM y NeurIPS), formulando el problema de tráfico urbano como un Dec-POMDP e implementando soluciones innovadoras como el enrutador GNNRouter para desviar vehículos ante congestión real de Waze. He superado exitosamente bloqueos de software desafiantes, como la estabilización de libsumo y la refactorización geométrica de la red vial."
        ),
        # Competencia 6
        (
            "6. Trabajo Colaborativo y Liderazgo Técnico",
            "Sello Institucional Duoc UC — Empleabilidad | Colaboración interdisciplinaria y prácticas profesionales en equipo.",
            2, # AD
            "Manejo herramientas de colaboración profesional (Git, GitHub, documentación de código y pull requests), facilitando la comunicación técnica con docentes guía y especialistas de transporte. Aunque este proyecto se ejecuta de forma individual, aplico estándares de desarrollo que permiten la integración fluida en equipos interdisciplinarios. Considero 'Alto Dominio' porque deseo seguir consolidando habilidades de liderazgo de equipos en proyectos de Machine Learning a gran escala."
        ),
        # Competencia 7
        (
            "7. Comunicación Integral y Difusión Técnica en Inglés",
            "Sello Institucional Duoc UC — Empleabilidad | Comunicación técnica efectiva en español y en inglés profesional.",
            2, # AD
            "Poseo excelente comprensión lectora de documentación técnica y papers científicos en inglés, y soy capaz de redactar abstracts, informes y documentación de código con precisión gramatical y técnica a nivel intermedio-alto. Marco 'Alto Dominio' porque requiero continuar fortaleciendo la fluidez estilística nativa y la argumentación oral espontánea en conferencias internacionales de Inteligencia Artificial."
        ),
        # Competencia 8
        (
            "8. Ética Profesional, Responsabilidad Social y Sostenibilidad",
            "Sello Institucional Duoc UC — Empleabilidad | Compromiso ciudadano, transparencia metodológica y sostenibilidad urbana.",
            1, # ED
            "Concibo la informática como una disciplina de servicio público que debe resolver problemas críticos de la sociedad. Mi proyecto aborda directamente la reducción de la congestión, el estrés urbano y las emisiones de CO2 en el Gran Santiago, utilizando exclusivamente datos abiertos de fuentes legítimas (OpenStreetMap, Waze) y garantizando la reproducibilidad científica y transparencia algorítmica de los resultados para la comunidad."
        )
    ]

    # Style Header rows (R0 and R1)
    for c in t2.rows[0].cells:
        set_cell_shading(c, "003366")
        set_cell_margins(c, 50, 50, 60, 60)
        for p in c.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                set_run_font(r, font_name="Century Gothic", size_pt=9.5, bold=True, color_rgb=RGBColor(255, 255, 255))

    for c in t2.rows[1].cells:
        set_cell_shading(c, "1B4F72")
        set_cell_margins(c, 50, 50, 60, 60)
        for p in c.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                set_run_font(r, font_name="Century Gothic", size_pt=8.5, bold=True, color_rgb=RGBColor(255, 255, 255))

    # Fill data rows (R2 to R9)
    for idx, (title, scope, level_col, comment) in enumerate(competencias_data):
        row = t2.rows[idx + 2]
        
        # Col 0: Competency name & description
        c0 = row.cells[0]
        p0 = clean_cell_first_paragraph(c0)
        p0.paragraph_format.space_before = Pt(2)
        p0.paragraph_format.space_after = Pt(2)
        p0.paragraph_format.line_spacing = 1.15
        r_title = p0.add_run(title + "\n")
        set_run_font(r_title, font_name="Century Gothic", size_pt=9, bold=True, color_rgb=RGBColor(0, 51, 102))
        r_scope = p0.add_run(scope)
        set_run_font(r_scope, font_name="Century Gothic", size_pt=8, italic=True, color_rgb=RGBColor(90, 90, 90))
        set_cell_margins(c0, 50, 50, 70, 70)

        # Cols 1 to 5: Achievement levels
        for col_i in range(1, 6):
            cell = row.cells[col_i]
            p = clean_cell_first_paragraph(cell)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(3)
            set_cell_margins(cell, 40, 40, 40, 40)
            
            if col_i == level_col:
                r_x = p.add_run("X")
                set_run_font(r_x, font_name="Century Gothic", size_pt=11, bold=True, color_rgb=RGBColor(0, 100, 0))
                set_cell_shading(cell, "E8F8F5")
            else:
                set_cell_shading(cell, "FFFFFF" if idx % 2 == 0 else "F9FAFA")

        # Col 6: Comments
        c6 = row.cells[6]
        p6 = clean_cell_first_paragraph(c6)
        p6.paragraph_format.space_before = Pt(2)
        p6.paragraph_format.space_after = Pt(2)
        p6.paragraph_format.line_spacing = 1.15
        r_comm = p6.add_run(comment)
        set_run_font(r_comm, font_name="Century Gothic", size_pt=8.5, color_rgb=RGBColor(30, 30, 30))
        set_cell_margins(c6, 50, 50, 70, 70)

    # -------------------------------------------------------------------------
    # 3. Append Synthesis Section at the end of the document
    # -------------------------------------------------------------------------
    p_sec = doc.add_paragraph()
    p_sec.paragraph_format.space_before = Pt(14)
    p_sec.paragraph_format.space_after = Pt(4)
    r_s_title = p_sec.add_run("Síntesis Diagnóstica y Plan de Acción de la Autoevaluación (Fase 1)")
    set_run_font(r_s_title, font_name="Century Gothic", size_pt=11, bold=True, color_rgb=RGBColor(0, 51, 102))

    sintesis_text = (
        "El análisis integral de la matriz de autoevaluación evidencia un estado de madurez destacado en las competencias disciplinarias centrales del perfil de egreso: Desarrollo de Soluciones de Software, Construcción de Modelos de Datos, Pruebas y Certificación de Software, e Innovación y Pensamiento Crítico, todas evaluadas en el nivel de 'Excelente Dominio (ED)'. Esto se sustenta en evidencias técnicas objetivas del proyecto APT: la implementación del arnés experimental en Python/SUMO, la arquitectura GNNRouter con PyTorch Geometric, la estabilización de la red vial Alameda-Providencia (certificada como APTA) y la tasa de aprobación del 100% en la suite de 12 pruebas automatizadas en pytest.\n"
        "Asimismo, las competencias calificadas en 'Alto Dominio (AD)' —Gestión de Proyectos, Trabajo Colaborativo y Comunicación Técnica en Inglés— delimitan las oportunidades concretas de perfeccionamiento para la Fase 3 del proyecto. En particular, se priorizará el estudio de arquitecturas de computación distribuida con Ray/RLlib para el escalado del algoritmo MAPPO/CTDE, el seguimiento riguroso de contingencias experimentales y el perfeccionamiento de la redacción técnica en inglés para la divulgación internacional de los hallazgos de titulación."
    )
    for par in sintesis_text.split('\n'):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(5)
        p.paragraph_format.line_spacing = 1.15
        r = p.add_run(par)
        set_run_font(r, font_name="Century Gothic", size_pt=9.5, color_rgb=RGBColor(40, 40, 40))

    output_path = "Reflexiones/1.1_APT122_AutoevaluacionCompetenciasFase1.docx"
    doc.save(output_path)
    print(f"Successfully updated and saved: {output_path}")

if __name__ == "__main__":
    populate_1_1()
