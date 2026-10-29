import os
import docx
from docx.shared import Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def set_run_font(run, font_name="Century Gothic", size_pt=11, bold=False, italic=False, color_rgb=None):
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

def set_cell_margins(cell, top=140, bottom=140, left=180, right=180):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def clear_cell_paragraphs(cell):
    # Keep the first paragraph and empty it, remove the rest
    p_first = cell.paragraphs[0]
    p_first.text = ""
    for p in cell.paragraphs[1:]:
        p._p.getparent().remove(p._p)
    return p_first

def add_styled_para(cell, text="", font_name="Century Gothic", size_pt=10.5, bold=False, italic=False, color_rgb=None, space_after=6, space_before=0):
    p = cell.add_paragraph()
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.15
    if text:
        run = p.add_run(text)
        set_run_font(run, font_name=font_name, size_pt=size_pt, bold=bold, italic=italic, color_rgb=color_rgb)
    return p

def add_header_prompt(cell, question_num, prompt_text):
    p = cell.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.15
    
    run_q = p.add_run(f"Pregunta {question_num}: ")
    set_run_font(run_q, font_name="Century Gothic", size_pt=11, bold=True, italic=False, color_rgb=RGBColor(0, 51, 102))
    
    run_t = p.add_run(prompt_text)
    set_run_font(run_t, font_name="Century Gothic", size_pt=10.5, bold=True, italic=False, color_rgb=RGBColor(30, 30, 30))
    return p

def populate_diario():
    doc_path = "Reflexiones/1.2_APT122_DiarioReflexionFase1.docx"
    doc = docx.Document(doc_path)

    # 1. Update Table 1 note / student identification
    t1_cell = doc.tables[1].rows[0].cells[0]
    # Add student banner inside Table 1 or below it
    p_banner = t1_cell.add_paragraph()
    p_banner.paragraph_format.space_before = Pt(6)
    p_banner.paragraph_format.space_after = Pt(4)
    run_b = p_banner.add_run("Estudiante: ")
    set_run_font(run_b, font_name="Century Gothic", size_pt=10, bold=True, color_rgb=RGBColor(0, 51, 102))
    run_b2 = p_banner.add_run("Gabriel Ignacio Cárdenas Valdés  |  ")
    set_run_font(run_b2, font_name="Century Gothic", size_pt=10, bold=False, color_rgb=RGBColor(50, 50, 50))
    run_b3 = p_banner.add_run("Carrera: ")
    set_run_font(run_b3, font_name="Century Gothic", size_pt=10, bold=True, color_rgb=RGBColor(0, 51, 102))
    run_b4 = p_banner.add_run("Ingeniería en Informática, Duoc UC  |  ")
    set_run_font(run_b4, font_name="Century Gothic", size_pt=10, bold=False, color_rgb=RGBColor(50, 50, 50))
    run_b5 = p_banner.add_run("Asignatura: ")
    set_run_font(run_b5, font_name="Century Gothic", size_pt=10, bold=True, color_rgb=RGBColor(0, 51, 102))
    run_b6 = p_banner.add_run("PTY4614 Capstone (APT122)")
    set_run_font(run_b6, font_name="Century Gothic", size_pt=10, bold=False, color_rgb=RGBColor(50, 50, 50))

    # =========================================================================
    # TABLE 2: Asignaturas y Certificaciones
    # =========================================================================
    cell2 = doc.tables[2].rows[1].cells[0]
    clear_cell_paragraphs(cell2)

    add_header_prompt(cell2, "1.1", "¿Cuáles son las asignaturas o certificados que más te gustaron y/o se relacionan con tus intereses profesionales? ¿Qué es lo que más te gustó de cada uno?")
    
    p = cell2.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run("A lo largo de mi trayectoria en la carrera de Ingeniería en Informática en Duoc UC, cuatro asignaturas y líneas de certificación definieron de manera decisiva mis intereses profesionales y vocación tecnológica:")
    set_run_font(r, font_name="Century Gothic", size_pt=10.5)

    asignaturas = [
        ("Inteligencia Artificial y Aprendizaje Automático (Machine Learning):",
         "Esta asignatura fue el detonante central de mi vocación por la investigación aplicada. Lo que más me apasionó fue comprender cómo los modelos computacionales pueden aprender dinámicas no lineales complejas y tomar decisiones secuenciales a partir de funciones de recompensa o datos empíricos. En particular, profundizar en el aprendizaje por refuerzo (RL) y su formalización matemática como procesos de decisión de Markov abrió la línea de investigación que hoy consolida mi proyecto de título en control adaptativo de tráfico."),
        ("Programación Avanzada, Estructuras de Datos y Algoritmos:",
         "Constituyó el núcleo fundamental para desarrollar software de alto rendimiento y complejidad algorítmica. Lo que más destaqué fue el análisis riguroso de complejidad temporal y espacial (notación Big-O), la implementación de estructuras de grafos dirigidos y el diseño orientado a la extensibilidad y bajo acoplamiento. Estas competencias resultaron críticas para construir los enrutadores neuronales sobre grafos (GNN) y procesar con fluidez las complejas topologías de red en simulación microscópica."),
        ("Calidad, Arquitectura y Pruebas de Software:",
         "Aprendí que un algoritmo matemático sofisticado carece de viabilidad profesional si no cuenta con una arquitectura mantenible y un aseguramiento de calidad automatizado. Me cautivó la adopción del desarrollo guiado por pruebas (TDD), la creación de suites automatizadas con pytest y el diseño modular limpio. Gracias a esta base, todo el pipeline experimental de mi tesis cuenta con 12/12 pruebas unitarias e integración pasando continuamente, garantizando reproducibilidad y solidez científica."),
        ("Modelamiento y Gestión de Bases de Datos:",
         "Me fascinó la disciplina para transformar entidades del mundo real en modelos lógicos y físicos escalables. El trabajo con motores relacionales y no relacionales me entregó la capacidad técnica de gestionar eficientemente grandes volúmenes de telemetría vehicular, series de tiempo y registros de métricas de tránsito generados durante las simulaciones.")
    ]

    for title, desc in asignaturas:
        p = cell2.add_paragraph()
        p.paragraph_format.left_indent = Pt(14)
        p.paragraph_format.space_after = Pt(4)
        r_t = p.add_run(f"• {title} ")
        set_run_font(r_t, font_name="Century Gothic", size_pt=10.5, bold=True, color_rgb=RGBColor(0, 51, 102))
        r_d = p.add_run(desc)
        set_run_font(r_d, font_name="Century Gothic", size_pt=10.5, color_rgb=RGBColor(40, 40, 40))

    add_header_prompt(cell2, "1.2", "A partir de las certificaciones que obtienes a lo largo de la carrera ¿Existe valor en la o las certificaciones obtenidas? ¿Por qué?")
    
    cert_text = (
        "Existe un valor sustantivo y estratégico de primer orden en las certificaciones académicas intermedias otorgadas por Duoc UC, tanto para la empleabilidad como para la maduración profesional del estudiante.\n"
        "Desde la perspectiva del mercado laboral, la industria tecnológica exige hoy garantías tangibles de competencia técnica comprobable bajo estándares de la industria (diseño de software modular, administración de modelos de datos, aseguramiento de la calidad mediante testing automatizado y gestión ágil). Contar con certificaciones curriculares intermedias valida formalmente ante los empleadores que el egresado no posee únicamente nociones abstractas, sino que ha sido evaluado bajo criterios de desempeño rigurosos y buenas prácticas de ingeniería.\n"
        "Desde la perspectiva formativa personal, estas certificaciones constituyen hitos de consolidación que otorgan la confianza metodológica para abordar desafíos de ingeniería de gran escala. En mi caso, las competencias certificadas en arquitectura de software y modelado de datos me capacitaron para liderar de forma autónoma una investigación de alta exigencia: diseñar un arnés experimental reproducible en Python/SUMO, desacoplar controladores clásicos y de RL, integrar telemetría de Waze en vivo y asegurar el 100% de cobertura mediante pruebas unitarias."
    )
    for par in cert_text.split('\n'):
        p = cell2.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        r = p.add_run(par)
        set_run_font(r, font_name="Century Gothic", size_pt=10.5, color_rgb=RGBColor(40, 40, 40))

    # =========================================================================
    # TABLE 3: Competencias (Verde = Fortalezas, Rojo = A fortalecer)
    # =========================================================================
    cell3 = doc.tables[3].rows[1].cells[0]
    clear_cell_paragraphs(cell3)

    p_intro = cell3.add_paragraph()
    p_intro.paragraph_format.space_before = Pt(6)
    p_intro.paragraph_format.space_after = Pt(6)
    r = p_intro.add_run("Matriz Diagnóstica de Competencias del Perfil de Egreso (Semáforo de Desempeño):")
    set_run_font(r, font_name="Century Gothic", size_pt=11, bold=True, color_rgb=RGBColor(0, 51, 102))

    competencias_verde = [
        ("Desarrollo de Soluciones de Software de Alto Rendimiento:",
         "Dominio integral de la programación en Python, arquitectura orientada a objetos modular, desacoplamiento de componentes e integración de APIs complejas en tiempo real (TraCI, libsumo, REST API de Waze). Capacidad probada para construir motores de inferencia y simulación robustos."),
        ("Pruebas y Certificación de Software Automatizadas:",
         "Diseño y ejecución rigurosa de suites de pruebas unitarias, de integración y regresión con pytest. Aplicación de validaciones invariantes de sanidad topológica (0 colisiones, 0 teletransportes) y verificación formal del código según estándares de calidad de la industria."),
        ("Construcción y Explotación de Modelos de Datos Topológicos y Espaciales:",
         "Modelado avanzado de redes viales complejas, transformación de capas OpenStreetMap en grafos dirigidos para Redes Neuronales Convolucionales (PyTorch Geometric) y procesamiento de series temporales de tráfico vehicular."),
        ("Investigación Aplicada y Autoaprendizaje Autónomo:",
         "Capacidad demostrada para analizar literatura científica especializada (IEEE Transactions, ACM, NeurIPS), asimilar frameworks de vanguardia (PettingZoo, Stable-Baselines3, SUMO-RL) y resolver incidencias técnicas en entornos de desarrollo desafiantes.")
    ]

    p_v_title = cell3.add_paragraph()
    p_v_title.paragraph_format.space_before = Pt(4)
    p_v_title.paragraph_format.space_after = Pt(4)
    r = p_v_title.add_run("🟢 COMPETENCIAS CLASIFICADAS EN VERDE (FORTALEZAS DESTACADAS):")
    set_run_font(r, font_name="Century Gothic", size_pt=10.5, bold=True, color_rgb=RGBColor(0, 128, 0))

    for title, desc in competencias_verde:
        p = cell3.add_paragraph()
        p.paragraph_format.left_indent = Pt(14)
        p.paragraph_format.space_after = Pt(3)
        r_t = p.add_run(f"• 🟢 {title} ")
        set_run_font(r_t, font_name="Century Gothic", size_pt=10, bold=True, color_rgb=RGBColor(0, 100, 0))
        r_d = p.add_run(desc)
        set_run_font(r_d, font_name="Century Gothic", size_pt=10, color_rgb=RGBColor(40, 40, 40))

    competencias_rojo = [
        ("Orquestación y Computación Distribuida a Gran Escala:",
         "Despliegue, sintonización y sincronización de clusters distribuidos de entrenamiento multi-nodo (Ray / RLlib) para arquitecturas de aprendizaje por refuerzo masivas (CTDE / MAPPO). Aunque domino la concurrencia multihilo local, la gestión de clusters en la nube es un área prioritaria a fortalecer."),
        ("Gestión Predictiva Formal de Proyectos frente a Incertidumbre en I+D:",
         "Planificación detallada bajo metodologías predictivas tradicionales frente a la variabilidad intrínseca de la investigación experimental. Requiero robustecer la estimación de contingencias formales cuando los resultados empíricos exigen re-formulación de hipótesis."),
        ("Redacción Académica y Divulgación Científica en Inglés Técnico Internacional:",
         "Redacción de artículos de investigación para conferencias internacionales indexadas con vocabulario estilístico nativo. Si bien poseo excelente comprensión y redacción funcional, busco elevar mi estándar de redacción al nivel de publicaciones internacionales.")
    ]

    p_r_title = cell3.add_paragraph()
    p_r_title.paragraph_format.space_before = Pt(8)
    p_r_title.paragraph_format.space_after = Pt(4)
    r = p_r_title.add_run("🔴 COMPETENCIAS CLASIFICADAS EN ROJO (ÁREAS QUE REQUIEREN FORTALECIMIENTO):")
    set_run_font(r, font_name="Century Gothic", size_pt=10.5, bold=True, color_rgb=RGBColor(178, 34, 34))

    for title, desc in competencias_rojo:
        p = cell3.add_paragraph()
        p.paragraph_format.left_indent = Pt(14)
        p.paragraph_format.space_after = Pt(3)
        r_t = p.add_run(f"• 🔴 {title} ")
        set_run_font(r_t, font_name="Century Gothic", size_pt=10, bold=True, color_rgb=RGBColor(139, 0, 0))
        r_d = p.add_run(desc)
        set_run_font(r_d, font_name="Century Gothic", size_pt=10, color_rgb=RGBColor(40, 40, 40))

    add_header_prompt(cell3, "2.1", "¿Cuáles consideras que tienes más desarrolladas y te sientes más seguro aplicando? ¿En cuáles te sientes más débil y requieren ser fortalecidas?")
    
    refl_q2 = (
        "Al reflexionar sobre mi desempeño concreto en el desarrollo del Proyecto APT, las competencias que tengo más afianzadas y en las que experimento plena seguridad operativa son la resolución algorítmica de problemas, el diseño de arquitecturas de software modulares, la manipulación de modelos de datos geoespaciales y el testing automatizado. La implementación del arnés experimental de la tesis —con 12 pruebas unitarias pasando al 100% y la certificación matemática de la red de Alameda-Providencia como 'APTA' por diagnose_net.py— es testimonio directo de esta solvencia técnica.\n"
        "Por otro lado, mis debilidades relativas se concentran en la administración de entornos distribuidos a gran escala (Ray/RLlib) y la formalización de planes predictivos para proyectos con riesgo de investigación. Reconocer estas brechas me ha permitido convertirlas en objetivos de superación concretos: me encuentro estudiando activamente la arquitectura interna de Ray para el escalado del entrenamiento MAPPO en la Fase 3, y he adoptado un esquema de gestión ágil por hitos quincenales verificables para controlar los riesgos del proyecto."
    )
    for par in refl_q2.split('\n'):
        p = cell3.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        r = p.add_run(par)
        set_run_font(r, font_name="Century Gothic", size_pt=10.5, color_rgb=RGBColor(40, 40, 40))

    # =========================================================================
    # TABLE 4: Intereses profesionales y perfil de egreso
    # =========================================================================
    cell4 = doc.tables[4].rows[1].cells[0]
    clear_cell_paragraphs(cell4)

    add_header_prompt(cell4, "3.1", "¿Cuáles son tus principales intereses profesionales? ¿Hay alguna área de desempeño que te interese más?")
    t4_1 = (
        "Mis principales intereses profesionales se sitúan en la intersección de tres pilares de la informática moderna: el Aprendizaje por Refuerzo (Reinforcement Learning), la Optimización Algorítmica sobre Grafos y los Sistemas de Transporte Inteligente (ITS).\n"
        "El área de desempeño que más me apasiona es la Ingeniería de Machine Learning (ML Engineering) aplicada a Sistemas Ciberfísicos e Infraestructuras Urbanas Inteligentes (Smart Cities). Me motiva de manera especial abordar problemas complejos y a gran escala donde interactúan múltiples agentes autónomos y dinámicas estocásticas en tiempo real. Resolver la sincronización de redes semafóricas comunales o la optimización de rutas vehiculares no es solo un apasionante desafío algorítmico, sino una oportunidad tangible de generar impacto social positivo: reducir tiempos de traslado, mitigar la congestión vial, ahorrar combustible y disminuir drásticamente la huella de carbono de nuestras ciudades."
    )
    for par in t4_1.split('\n'):
        p = cell4.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        r = p.add_run(par)
        set_run_font(r, font_name="Century Gothic", size_pt=10.5, color_rgb=RGBColor(40, 40, 40))

    add_header_prompt(cell4, "3.2", "¿Cuáles son las principales competencias que se relacionan con tus intereses profesionales? ¿Hay alguna de ellas que sientas que requieres especialmente fortalecer?")
    t4_2 = (
        "Las principales competencias del perfil de egreso estrechamente vinculadas a mis intereses profesionales son:\n"
        "1. Desarrollo de Soluciones de Software de Alto Rendimiento: Indispensable para programar sistemas de control e inferencia con tiempos de respuesta críticos en milisegundos, interactuando con simuladores de tráfico y sensores en tiempo real.\n"
        "2. Construcción de Modelos de Datos Escalables y Representaciones Espaciales: Fundamental para estructurar redes de transporte como grafos de conocimiento y alimentarlos a redes neuronales convolucionales de grafos (GNN).\n"
        "3. Aseguramiento de Calidad y Pruebas Automatizadas: En infraestructuras públicas críticas, un fallo de software o un error lógico en un controlador semafórico puede ocasionar bloqueos masivos o riesgos a la seguridad vial; por ello, la verificación rigurosa es no negociable.\n"
        "Competencia que requiero fortalecer especialmente: La competencia de Implantación y Despliegue en Producción (MLOps). Deseo robustecer mis habilidades en la containerización de pipelines de ML con Docker/Kubernetes, la monitorización continua del desvío de datos de tráfico (data drift) y la automatización del ciclo de reentrenamiento de agentes en producción."
    )
    for par in t4_2.split('\n'):
        p = cell4.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        r = p.add_run(par)
        set_run_font(r, font_name="Century Gothic", size_pt=10.5, color_rgb=RGBColor(40, 40, 40))

    add_header_prompt(cell4, "3.3", "¿Cómo te gustaría que fuera tu escenario laboral en 5 años más? ¿Qué te gustaría estar haciendo?")
    t4_3 = (
        "En un horizonte de cinco años, me proyecto consolidado profesionalmente como Machine Learning Engineer Senior o Tech Lead en Soluciones de Inteligencia Artificial y Movilidad Urbana, trabajando en una empresa de tecnología líder, un centro de innovación avanzada o en organismos gubernamentales y privados encargados de la gestión de transporte (como la Unidad Operativa de Control de Tránsito - UOCT o consultoras internacionales de ingeniería de transporte).\n"
        "En este escenario, me veo liderando equipos interdisciplinarios dedicados a diseñar, entrenar y desplegar en producción sistemas multi-agente para la toma de decisiones autónoma en infraestructuras metropolitanas. Me gustaría estar a cargo de arquitecturas de software que optimicen flujos vehiculares y logísticos a nivel de ciudad, integrando sensores IoT, gemelos digitales y modelos predictivos para transformar las metrópolis en espacios más eficientes, sustentables y habitables."
    )
    for par in t4_3.split('\n'):
        p = cell4.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        r = p.add_run(par)
        set_run_font(r, font_name="Century Gothic", size_pt=10.5, color_rgb=RGBColor(40, 40, 40))

    # =========================================================================
    # TABLE 5: Conexión con el Proyecto APT
    # =========================================================================
    cell5 = doc.tables[5].rows[1].cells[0]
    clear_cell_paragraphs(cell5)

    add_header_prompt(cell5, "4.1", "Los Proyectos APT que ya habías diseñado como plan de trabajo en el curso anterior, ¿se relacionan con tus proyecciones profesionales actuales? ¿cuál se relaciona más? ¿Requiere ajuste?")
    t5_1 = (
        "El Proyecto APT seleccionado —'Control adaptativo de semáforos mediante aprendizaje por refuerzo multi-agente: Evaluación comparativa frente a estrategias clásicas de control en una red a nivel comunal de Santiago de Chile'— guarda una relación directa, estratégica y total con mis proyecciones profesionales en el área de Inteligencia Artificial aplicada.\n"
        "Ajuste fundamental implementado: En la formulación inicial del anteproyecto, el plan de trabajo consideraba exclusivamente la experimentación sobre un escenario sintético uniforme (una grilla hipotética de 4x4 intersecciones). Si bien este entorno permitió verificar la estabilidad inicial del bucle de control, comprendí tempranamente que los resultados en una red abstracta carecen de validez empírica transferible y de relevancia práctica para el contexto profesional chileno.\n"
        "Por esta razón, realicé un ajuste ambicioso y decisivo: elevar el escenario experimental a un corredor urbano de escala comunal real del Gran Santiago —el eje Alameda-Providencia, con 37 intersecciones semaforizadas y 4.8 km de extensión—. Este ajuste demandó un riguroso trabajo de ingeniería de software:\n"
        "1. Depuración geométrica y semafórica de la red real con SUMO y NETCONVERT, eliminando cuellos de botella y semáforos monopolares hasta lograr la certificación 'APTA' por diagnose_net.py (0 colisiones y 0 teletransportes en simulación).\n"
        "2. Generación y formalización de cuatro perfiles de demanda horaria diferenciada (valle, punta mañana, punta tarde y sobresaturado) con sesgos direccionales calibrados.\n"
        "3. Integración de telemetría de congestión real en vivo mediante la API de Waze y un enrutador inteligente basado en Redes Neuronales Convolucionales sobre Grafos (GNN).\n"
        "Este ajuste transformó el proyecto de un ejercicio académico abstracto a un estudio de ingeniería aplicada de vanguardia con alta relevancia para la industria y el sector público."
    )
    for par in t5_1.split('\n'):
        p = cell5.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        r = p.add_run(par)
        set_run_font(r, font_name="Century Gothic", size_pt=10.5, color_rgb=RGBColor(40, 40, 40))

    add_header_prompt(cell5, "4.2", "Si no hay ninguna que se relacione suficiente: ¿Qué área(s) de desempeño y competencias debería abordar este Proyecto APT? ¿Qué tipo de proyecto podría ayudarte más en tu desarrollo profesional? ¿En qué contexto se debería situar este Proyecto APT?")
    t5_2 = (
        "Dado que el proyecto seleccionado está plenamente alineado con mis proyecciones, satisface de manera integral todas las condiciones para potenciar mi inserción profesional:\n"
        "• Áreas de desempeño abordadas: Machine Learning Engineering, Simulación Microscópica de Tráfico, Optimización Matemática Combinatoria y Computación de Grafos.\n"
        "• Competencias del perfil de egreso movilizadas: Integra simultáneamente las cuatro competencias del perfil: desarrollo de soluciones de software de alto rendimiento, ejecución de pruebas de calidad automatizadas (pytest), diseño de modelos de datos complejos y gestión estructurada de proyectos informáticos.\n"
        "• Tipo de proyecto de máximo impacto formativo: Una evaluación comparativa rigurosa (benchmarking) entre estrategias de control clásicas consolidadas (Tiempo Fijo, Webster, Max-Pressure) y agentes adaptativos modernos basados en aprendizaje por refuerzo multi-agente (IPPO y MAPPO). Este enfoque metodológico garantiza hallazgos de alto valor científico y técnico independientemente del resultado de los agentes de RL, eliminando los riesgos de una propuesta puramente experimental.\n"
        "• Contexto de aplicación idóneo: El contexto ineludible es el Gran Santiago, utilizando una arteria estructurante real como Alameda-Providencia y datos empíricos de tráfico. Esto demuestra cómo la ingeniería informática puede resolver problemáticas críticas de transporte público y privado, aportando innovación tangible a la gestión metropolitana de nuestro país."
    )
    for par in t5_2.split('\n'):
        p = cell5.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        r = p.add_run(par)
        set_run_font(r, font_name="Century Gothic", size_pt=10.5, color_rgb=RGBColor(40, 40, 40))

    output_path = "Reflexiones/1.2_APT122_DiarioReflexionFase1.docx"
    doc.save(output_path)
    print(f"Successfully updated and saved: {output_path}")

if __name__ == "__main__":
    populate_diario()
