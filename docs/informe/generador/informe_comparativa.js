// Informe Word de la comparativa de controladores (7-nov-2026).
// Las cifras de las tablas se calculan aquí desde los JSON de resultados, no se copian a mano.
//
//   cd docs/informe/generador && npm install && node informe_comparativa.js
//   (antes: python docs/informe/generador/figuras_comparativa.py desde la raíz)
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, HeadingLevel, LevelFormat, BorderStyle, Header, Footer, PageNumber, TabStopType,
} = require("docx");

const RAIZ = path.resolve(__dirname, "..", "..", "..");
const RES = path.join(RAIZ, "tsc-thesis", "results");
const FIG = path.join(RAIZ, "docs", "informe", "figuras", "comparativa");
const SALIDA = path.join(RAIZ, "docs", "informe", "informe-comparativa-controladores-2026-11-07.docx");

// ---------- datos ----------
const PERFILES = [["valle", "Valle"], ["punta_manana", "Punta mañana"], ["punta_tarde", "Punta tarde"], ["sobresaturado", "Sobresaturado"]];
const CTRL = [["fixed", "Tiempo fijo"], ["webster", "Webster"], ["maxpressure", "Max-Pressure"], ["greedy", "Voraz"],
  ["ppo_fase_s0", "IPPO s0"], ["ppo_fase_s1", "IPPO s1"]];
const CLASICOS = ["fixed", "webster", "maxpressure", "greedy"];
const media = a => a.reduce((x, y) => x + y, 0) / a.length;
const ic95 = a => { const m = media(a); return 1.96 * Math.sqrt(a.reduce((s, x) => s + (x - m) ** 2, 0) / (a.length - 1)) / Math.sqrt(a.length); };
const R = {};
for (const [p] of PERFILES) {
  R[p] = {};
  for (const r of JSON.parse(fs.readFileSync(path.join(RES, `eje_comunal_${p}_baselines.json`), "utf8"))) {
    (R[p][r.controller] ??= []).push(r);
  }
}
const met = (p, c, k) => R[p][c].map(r => r[k]);
const dem = (p, c) => media(met(p, c, "delay_all_mean"));
const mejorClasico = p => CLASICOS.reduce((a, b) => (dem(p, a) <= dem(p, b) ? a : b));
const n1 = x => x.toLocaleString("es-CL", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const n0 = x => Math.round(x).toLocaleString("es-CL");
const pct = x => (x > 0 ? "+" : "−") + Math.abs(x * 100).toLocaleString("es-CL", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " %";
const NOMBRE = Object.fromEntries(CTRL);
const NOMBRE_LARGO = { fixed: "tiempo fijo", webster: "Webster", maxpressure: "Max-Pressure", greedy: "el controlador voraz" };
for (const [p] of PERFILES) for (const [c] of CTRL) if (!R[p][c] || R[p][c].length !== 10) throw new Error(`faltan réplicas ${p}/${c}`);

// ---------- estilo ----------
const FUENTE = "Arial", AZUL = "1F3A4D", GRIS = "5A5A5A", BORDE = "BFC7CC", CABECERA = "E8EEF2", RESALTE = "DDEBF7";
const ANCHO = 9026; // A4 con márgenes de 2,54 cm
const t = (texto, o = {}) => new TextRun({ text: texto, font: FUENTE, ...o });
const P = (partes, o = {}) => new Paragraph({ spacing: { after: 120, line: 288 }, ...o,
  children: (Array.isArray(partes) ? partes : [partes]).map(x => (typeof x === "string" ? t(x) : x)) });
const H1 = s => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t(s)] });
const H2 = s => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [t(s)] });
const viñeta = (partes) => new Paragraph({ numbering: { reference: "vinetas", level: 0 }, spacing: { after: 80, line: 276 },
  children: (Array.isArray(partes) ? partes : [partes]).map(x => (typeof x === "string" ? t(x) : x)) });
const b = s => t(s, { bold: true });
const leyenda = s => new Paragraph({ spacing: { before: 60, after: 240 }, keepLines: true,
  children: [t(s, { italics: true, size: 18, color: GRIS })] });

function tamPng(f) { const buf = fs.readFileSync(f); return [buf.readUInt32BE(16), buf.readUInt32BE(20)]; }
function figura(archivo, anchoPx = 600) {
  const f = path.join(FIG, archivo), [w, h] = tamPng(f);
  return new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 0 },
    children: [new ImageRun({ type: "png", data: fs.readFileSync(f), transformation: { width: anchoPx, height: Math.round(anchoPx * h / w) } })] });
}

const bordes = { top: { style: BorderStyle.SINGLE, size: 4, color: BORDE }, bottom: { style: BorderStyle.SINGLE, size: 4, color: BORDE },
  left: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" }, right: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" } };
function celda(texto, ancho, o = {}) {
  return new TableCell({ width: { size: ancho, type: WidthType.DXA }, borders: bordes,
    shading: o.fondo ? { type: ShadingType.CLEAR, color: "auto", fill: o.fondo } : undefined,
    margins: { top: 60, bottom: 60, left: 90, right: 90 },
    children: [new Paragraph({ alignment: o.izq ? AlignmentType.LEFT : AlignmentType.RIGHT,
      children: [t(texto, { size: 17, bold: !!o.negrita })] })] });
}
function tabla(cabecera, filas, anchos, resaltar = () => false, texto = false) {
  // texto = true: todas las columnas son texto y van alineadas a la izquierda
  const izq = i => i === 0 || texto;
  return new Table({ width: { size: ANCHO, type: WidthType.DXA }, columnWidths: anchos,
    rows: [new TableRow({ tableHeader: true, cantSplit: true, children: cabecera.map((c, i) => celda(c, anchos[i], { izq: izq(i), negrita: true, fondo: CABECERA })) }),
      ...filas.map((f, r) => new TableRow({ cantSplit: true, children: f.map((c, i) => celda(c, anchos[i],
        { izq: izq(i), fondo: resaltar(r, i) ? RESALTE : undefined, negrita: resaltar(r, i) })) }))] });
}
const repartir = (primera, n) => { const resto = Math.floor((ANCHO - primera) / n); return [ANCHO - resto * n, ...Array(n).fill(resto)]; };

// ---------- cifras del texto ----------
const pt = "punta_tarde", so = "sobresaturado";
const vsMejor = p => dem(p, "ppo_fase_s1") / dem(p, mejorClasico(p)) - 1;
const vs = (p, c, ip = "ppo_fase_s1") => dem(p, ip) / dem(p, c) - 1;

// ---------- tablas ----------
const anchosT2 = repartir(1700, 6);
const T2 = tabla(["Perfil", ...CTRL.map(c => c[1])],
  PERFILES.map(([p, n]) => [n, ...CTRL.map(([c]) => `${n1(dem(p, c))} ± ${n1(ic95(met(p, c, "delay_all_mean")))}`)]),
  anchosT2, (r, i) => { const p = PERFILES[r][0], c = CTRL[i - 1]?.[0]; if (!c) return false;
    return dem(p, c) === Math.min(...CTRL.map(([k]) => dem(p, k))); });
const T3 = tabla(["Perfil", "Mejor clásico", "IPPO vs. mejor clásico", "IPPO vs. Max-Pressure", "IPPO vs. Webster", "IPPO vs. tiempo fijo"],
  PERFILES.map(([p, n]) => [n, NOMBRE[mejorClasico(p)], pct(vsMejor(p)), pct(vs(p, "maxpressure")), pct(vs(p, "webster")), pct(vs(p, "fixed"))]),
  repartir(1500, 5));
const T4 = tabla(["Controlador", "Espera p95 (s), punta tarde", "Vehículos/h, punta tarde", "Espera p95 (s), sobresaturado", "Vehículos/h, sobresaturado"],
  CTRL.map(([c, n]) => [n, n0(media(met(pt, c, "waiting_time_p95"))), n0(media(met(pt, c, "throughput"))),
    n0(media(met(so, c, "waiting_time_p95"))), n0(media(met(so, c, "throughput")))]), repartir(1826, 4));
const T1 = tabla(["Controlador", "Tipo", "Configuración evaluada"], [
  ["Tiempo fijo", "Plan fijo de la red importada", "Programas de OpenStreetMap/netconvert, sin optimizar"],
  ["Webster", "Plan fijo optimizado", "Ciclo y repartos de Webster por cruce; ciclo máximo 120 s; flujos medidos con el controlador voraz; sin ciclo común"],
  ["Max-Pressure", "Adaptativo, sin aprendizaje", "Presión por conteo de vehículos, sin histéresis; decide cada 5 s"],
  ["Voraz por cola", "Adaptativo, sin aprendizaje", "Da verde a la fase con más vehículos detenidos; decide cada 5 s"],
  ["IPPO", "Aprendido (PPO, parámetros compartidos)", "Observación por fase de 22 columnas; recompensa por variación de la espera; Adam; 2 millones de muestras; entrenado solo con punta tarde"],
], [1700, 2300, 5026], () => false, true);

// ---------- documento ----------
const hoy = "7 de noviembre de 2026";
const cuerpo = [
  new Paragraph({ spacing: { after: 60 }, children: [t("DUOC UC · Escuela de Informática y Telecomunicaciones · Ingeniería en Informática", { size: 18, color: GRIS })] }),
  new Paragraph({ heading: HeadingLevel.TITLE, children: [t("Comparativa de control de semáforos: tiempo fijo frente a control aprendido")] }),
  new Paragraph({ spacing: { after: 60 }, children: [t("Eje comunal Alameda – Providencia – Apoquindo, simulación en SUMO", { size: 24, color: AZUL })] }),
  new Paragraph({ spacing: { after: 320 }, border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: BORDE, space: 8 } },
    children: [t(`Gabriel Ignacio Cárdenas Valdés · ${hoy} · Informe de avance de tesis`, { size: 19, color: GRIS })] }),

  H1("1. Resumen"),
  P([`Se comparó un agente de aprendizaje por refuerzo multi-agente (IPPO) con cuatro controladores clásicos sobre la red del eje comunal: 64 semáforos en 13,6 km, de Matucana al final de Av. Apoquindo. En punta tarde, el perfil con el que se entrenó, IPPO obtiene ${n1(dem(pt, "ppo_fase_s1"))} s de demora media por vehículo, frente a ${n1(dem(pt, "fixed"))} s del tiempo fijo y ${n1(dem(pt, mejorClasico(pt)))} s del mejor controlador clásico (${pct(vsMejor(pt))}).`]),
  P("Tres resultados principales:"),
  viñeta([b("Generaliza a perfiles que no vio. "), `Supera al mejor clásico en punta mañana (${pct(vsMejor("punta_manana"))}) y sobresaturado (${pct(vsMejor(so))}). Solo en valle queda levemente detrás de Max-Pressure (${pct(vsMejor("valle"))}).`]),
  viñeta([b("La ventaja crece con la congestión. "), `Frente a Max-Pressure pasa de ${pct(vs("valle", "maxpressure"))} en valle a ${pct(vs(so, "maxpressure"))} en sobresaturado, en la dirección que plantea la hipótesis H2.`]),
  viñeta([b("Las cifras son provisionales. "), "La demanda es sintética y todavía no se valida con la medición de terreno, así que estos resultados muestran que el agente aprende; no contrastan aún las hipótesis de la tesis."]),

  H1("2. Escenario y método"),
  H2("2.1 Red y demanda"),
  P("La red se construyó desde OpenStreetMap: 1 130 arcos y 86 semáforos, de los cuales 64 están sobre el eje y son los que controla cada método. Los 22 de las calles transversales mantienen su programa de tiempo fijo en todos los casos, de modo que la comparación solo cambia el control del eje."),
  P("Se usan cuatro perfiles sintéticos de una hora: valle, punta mañana (flujo dominante de poniente a oriente), punta tarde (de oriente a poniente) y sobresaturado (130 % de punta tarde). De cada perfil se generaron demandas distintas para entrenar y para evaluar. La demanda de evaluación k se usa con la semilla k en todos los controladores, así que la comparación es pareada y el agente nunca se mide sobre viajes que vio al entrenar."),
  H2("2.2 Controladores"),
  T1,
  leyenda("Tabla 1. Controladores comparados. Todos los adaptativos respetan verde mínimo de 10 s, verde máximo de 60 s y ámbar de 3 s, y controlan los mismos 64 semáforos."),
  P("Max-Pressure y Webster se ajustaron antes de la comparación, solo con demandas de entrenamiento, para que la ventaja del agente no se deba a líneas base mal configuradas. Max-Pressure bajó de 219 a 111 s y Webster de 330 a 179 s en esas demandas. El principal cambio en Webster fue medir los flujos con un controlador que deja pasar la demanda: con tiempo fijo y la red congestionada se mide lo que el semáforo deja pasar, no lo que llega."),
  H2("2.3 Métricas y verificación"),
  P("La métrica principal es la demora media por vehículo incluyendo a los que no terminaron su viaje al cerrar la hora: los que siguen dentro de la red y los que esperan entrar. Así, un controlador que satura la red no sale favorecido porque esos vehículos desaparezcan del promedio. Se informan además la espera del percentil 95, que muestra a quién se sacrifica, y los vehículos que terminan su viaje por hora."),
  P("El agente corre sobre sumo-rl y los clásicos sobre el arnés propio del proyecto. Para descartar que la diferencia venga de cómo se mide, la misma regla voraz se ejecutó en ambos: 109,4 s y 110,3 s de demora (+0,8 %, 3 réplicas)."),

  H1("3. Resultados"),
  H2("3.1 Demora por perfil"),
  figura("fig1_demora_perfiles.png"),
  leyenda("Figura 1. Demora media por vehículo, incluidos los no terminados. Promedio de 10 demandas de evaluación por perfil; IPPO corresponde al modelo de semilla 1. Cada panel tiene su propia escala."),
  T2,
  leyenda("Tabla 2. Demora media ± intervalo de confianza del 95 % (s), 10 réplicas pareadas. En azul, el menor valor de cada perfil. IPPO s0 e IPPO s1 son dos entrenamientos independientes con la misma configuración."),
  P(`Los dos entrenamientos de IPPO llegan a resultados casi iguales en punta tarde (${n1(dem(pt, "ppo_fase_s0"))} y ${n1(dem(pt, "ppo_fase_s1"))} s) y con intervalos estrechos, lo que indica que el aprendizaje es estable. En los perfiles con congestión, Max-Pressure es el controlador más variable entre réplicas.`),
  T3,
  leyenda("Tabla 3. Cambio en la demora de IPPO (semilla 1) frente a cada controlador clásico. Negativo = IPPO tiene menos demora."),
  P("Con 10 pares, el valor p de la prueba de Wilcoxon pareada contra el mejor clásico es 0,002 en los cuatro perfiles. Es el mínimo posible con ese número de pares, por lo que no distingue diferencias grandes de pequeñas; por eso se informan los porcentajes y los intervalos."),
  T4,
  leyenda("Tabla 4. Espera del percentil 95 y vehículos que terminan su viaje por hora, promedio de 10 réplicas."),
  P("IPPO baja también la espera de los vehículos más perjudicados: en punta tarde el percentil 95 queda por debajo de 100 s, frente a más de 800 s con tiempo fijo. Al mismo tiempo deja pasar más vehículos por hora, de modo que la menor demora no se obtiene reteniendo vehículos fuera de la red."),

  H2("3.2 Dónde y cuándo se forma la cola"),
  figura("fig2_mapa_punta_tarde.png"),
  leyenda("Figura 2. Diagrama espacio-tiempo de colas en punta tarde. Eje horizontal: posición a lo largo del eje desde Matucana; eje vertical: minuto de la simulación; color: vehículos detenidos en las entradas de los semáforos de cada tramo de 500 m, en bloques de 4 minutos. Las líneas punteadas separan aproximadamente Alameda, Providencia y Apoquindo. Una demanda de evaluación."),
  P("Con tiempo fijo la cola se instala desde los primeros minutos en tres zonas: el final de Apoquindo (km 11,5 a 13), Providencia cerca del km 6,5 y varios tramos de la Alameda. Webster reduce las colas, pero mantiene las de Providencia y Apoquindo. Los tres adaptativos casi las eliminan, e IPPO es el que deja menos cola en el eje."),
  figura("fig3_mapa_sobresaturado.png"),
  leyenda("Figura 3. Mismo diagrama para el perfil sobresaturado, con su propia escala de color."),
  P("En sobresaturado la diferencia se acentúa. Max-Pressure, que en punta tarde era competitivo, forma colas que crecen durante la hora en Providencia (km 6,5) y en Apoquindo (km 11 a 12). IPPO las mantiene acotadas."),
  figura("fig4_detenidos_red.png"),
  leyenda("Figura 4. Vehículos detenidos en toda la red (incluidas las transversales), media móvil de 3 minutos. Una demanda de evaluación por perfil."),
  P("La Figura 4 muestra la misma conclusión a nivel de red. Con tiempo fijo los detenidos crecen durante toda la hora, señal de que la red no logra despachar la demanda. Con los adaptativos se estabilizan, salvo Webster y Max-Pressure en sobresaturado, que siguen creciendo."),

  H2("3.3 Visualización de la simulación"),
  P("Para mostrar la diferencia de forma directa se generaron videos de la ejecución real, cuadro a cuadro: cada vehículo en su posición y con su velocidad, y cada semáforo con su color. Los videos están en tsc-thesis/results/video/."),
  figura("fig5_video_apoquindo.png", 600),
  leyenda("Figura 5. Cuadro del minuto 30 en el tramo de Apoquindo oriente, punta tarde. Rojo = vehículo detenido; los círculos son los semáforos con su color. Con tiempo fijo hay 744 vehículos detenidos en la red; con IPPO, 52."),
  figura("fig6_video_eje_completo.png", 440),
  leyenda("Figura 6. Eje completo en el perfil sobresaturado, minuto 32: tiempo fijo arriba e IPPO abajo."),

  H1("4. Análisis"),
  viñeta([b("Por qué gana IPPO. "), "Decide con información que los planes fijos no usan: densidad y cola de cada fase y ocupación de las salidas. Max-Pressure usa información parecida con una regla fija; una explicación posible de la diferencia en sobresaturado es que el agente aprendió cuándo conviene sostener una fase, algo que la regla no considera. Confirmarlo requiere analizar las decisiones del agente, pendiente."]),
  viñeta([b("Hipótesis H1. "), `IPPO reduce la demora ${pct(vs(pt, "webster"))} frente a Webster en punta tarde, por sobre el umbral de 10 % que plantea H1. No se da por contrastada porque la demanda no está validada.`]),
  viñeta([b("Hipótesis H2. "), "La ventaja sobre Max-Pressure es menor que sobre tiempo fijo en todos los perfiles y crece con la congestión, como plantea H2. Queda sujeta a la misma condición."]),
  viñeta([b("Hipótesis H3. "), "No se evalúa en este informe: requiere el esquema de entrenamiento centralizado (MAPPO), aún no implementado."]),
  viñeta([b("Punta mañana. "), "Tiene más demora que punta tarde aunque su demanda es menor. La cola se concentra en Av. Providencia y Av. Nueva Providencia; es un rasgo de cómo el perfil sintético carga ese par de vías, y debe revisarse al validar la demanda."]),

  H1("5. Limitaciones"),
  viñeta([b("Demanda sintética. "), "Los perfiles se generaron con pesos de origen y destino fijados a mano. El resultado de tesis exige validarlos con la medición de terreno y reentrenar."]),
  viñeta([b("Tiempos semafóricos estimados. "), "El tiempo fijo usa los programas de la red importada, no la programación de la UOCT; por eso es un piso de comparación. La referencia de plan fijo bien calculado es Webster, y las más exigentes son los adaptativos."]),
  viñeta([b("Una demanda en los mapas. "), "Las Figuras 2 a 6 muestran una sola demanda de evaluación; las tablas promedian 10."]),
  viñeta([b("Ajuste acotado de los clásicos. "), "Max-Pressure se ajustó solo con punta tarde y 3 demandas; un ajuste por perfil podría acortar la diferencia en sobresaturado."]),
  viñeta([b("Observabilidad. "), "El agente usa densidad y cola por pista, una información más rica que la que entregan los detectores instalados hoy."]),
  viñeta([b("Simulación. "), "Los resultados valen dentro del modelo de SUMO; su traslado a la operación real queda fuera del alcance."]),

  H1("6. Próximos pasos"),
  viñeta("Validar la demanda con la medición de terreno de los 13 cruces y con tiempos de viaje por franja, y repetir entrenamiento y comparación."),
  viñeta("Implementar el esquema centralizado (MAPPO) en el tramo de Providencia para contrastar H3."),
  viñeta("Ejecutar las dos perturbaciones de robustez (cierre de un carril y alza de 30 % en un acceso) sobre la política final."),
  viñeta("Aumentar a 20 réplicas en la evaluación final si el tiempo de cómputo lo permite."),

  H1("Anexo. Reproducibilidad"),
  P("Todos los resultados se regeneran desde el repositorio (tsc-thesis/). Las demandas de entrenamiento y evaluación y los modelos entrenados no se versionan: se regeneran con los comandos siguientes."),
  ...[
    "python scripts/build_demand_profiles.py --scenario scenarios/eje_comunal --train-replicas 10 --eval-replicas 10",
    ".\\scripts\\lanzar_entrenamiento.ps1 -Corridas \"fase:0\",\"fase:1\" -Pasos 2000000",
    "python scripts/ajustar_baselines.py --scenario scenarios/eje_comunal --profile punta_tarde --flujos voraz",
    "python scripts/build_webster.py --scenario scenarios/eje_comunal --profile <perfil>",
    "python scripts/run_baselines.py --scenario scenarios/eje_comunal --profile <perfil> --seeds 10",
    "python scripts/eval_rl.py --scenario scenarios/eje_comunal --profile <perfil> --seeds 10 --model <modelo.zip>",
    "python scripts/verificar_paridad.py --scenario scenarios/eje_comunal --profile punta_tarde",
    "python scripts/medir_colas_eje.py --scenario scenarios/eje_comunal --profile <perfil> --controller <ctrl> --out <json>",
    "python scripts/video_comparativo.py --scenario scenarios/eje_comunal --profile punta_tarde --controllers fixed,ppo ...",
  ].map(c => new Paragraph({ spacing: { after: 40 }, indent: { left: 360 }, children: [t(c, { font: "Consolas", size: 16 })] })),
  P(["Decisiones registradas: ", t("docs/decisiones/08-decision-tiempos-semaforicos.md", { italics: true }), " y ", t("docs/decisiones/11-decision-agente.md", { italics: true }), ". Estado del proyecto: ", t("ESTADO_DEL_PROYECTO.md", { italics: true }), ", sección 6.6."], { spacing: { before: 160, after: 120 } }),
];

const doc = new Document({
  creator: "Gabriel Ignacio Cárdenas Valdés",
  title: "Comparativa de control de semáforos: tiempo fijo frente a control aprendido",
  styles: {
    default: { document: { run: { font: FUENTE, size: 21 } } },
    paragraphStyles: [
      { id: "Title", name: "Title", basedOn: "Normal", next: "Normal", run: { font: FUENTE, size: 40, bold: true, color: "16181A" }, paragraph: { spacing: { before: 0, after: 120 }, keepNext: true } },
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FUENTE, size: 28, bold: true, color: AZUL }, paragraph: { spacing: { before: 300, after: 120 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FUENTE, size: 23, bold: true, color: "16181A" }, paragraph: { spacing: { before: 200, after: 80 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: "vinetas", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 360, hanging: 260 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
      children: [t("Comparativa de controladores · eje comunal", { size: 16, color: GRIS })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [t("Página ", { size: 16, color: GRIS }), new TextRun({ children: [PageNumber.CURRENT], font: FUENTE, size: 16, color: GRIS }),
        t(" de ", { size: 16, color: GRIS }), new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FUENTE, size: 16, color: GRIS })] })] }) },
    children: cuerpo,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(SALIDA, buf);
  console.log("OK", SALIDA, buf.length, "bytes");
  for (const [p, n] of PERFILES) console.log(n, "mejor clásico:", NOMBRE[mejorClasico(p)], "IPPO s1 vs mejor:", pct(vsMejor(p)));
});
