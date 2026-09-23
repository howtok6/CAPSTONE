# Documentos de la tesis

Control adaptativo de semáforos mediante aprendizaje por refuerzo multi-agente
Gabriel Cárdenas · Ingeniería en Informática, DUOC UC

Última actualización: 24 de agosto de 2026.

## Qué hay aquí

| Archivo | Qué es | Cuándo mirarlo |
|---|---|---|
| `Anteproyecto_Tesis_Semaforos_Adaptativos.docx` | Anteproyecto formal, 18 páginas. Problema, objetivos, hipótesis, marco teórico, metodología, cronograma y bibliografía. | Es el documento que va al profesor guía. El `.pdf` es la misma versión, para leer sin Word. |
| `01-anteproyecto-v1.md` | El mismo anteproyecto en texto plano. | Para buscar, citar o copiar fragmentos sin abrir Word. |
| `02-windows-vs-wsl2.md` | Dónde montar el entorno, y la corrección de una recomendación anterior que estaba equivocada. | Decisión vigente: Windows nativo. |
| `03-montaje-wsl2.md` | Runbook paso a paso de WSL2, con verificación en cada paso. | Solo si migras a WSL2 (probablemente en la fase de MAPPO). |
| `04-entorno-y-stack.md` | El stack elegido capa por capa, la red comunal, resultados de sanidad y las trampas encontradas. | Referencia técnica general del proyecto. |
| `05-visualizacion.md` | Cómo ver la simulación en vivo y cómo grabar video. | Cuando quieras mirar o mostrar la ejecución. |
| `06-fuentes-de-datos.md` | De dónde sacar flujos, tiempos de viaje y programación real de semáforos, con la solicitud de transparencia lista. | Ahora. Las solicitudes tardan semanas. |

## Estado del proyecto

- **Red elegida:** Nivel comunal, abarcando información de tránsito de todas las comunas. Múltiples ejes y redes de intersecciones semaforizadas.
- **Entorno:** Windows nativo. Todo el stack tiene rueda de Windows, incluido
  `libsumo`, y las pruebas ya pasan en esta máquina.
- **Pipeline:** funcionando de punta a punta — escenario, cuatro controladores
  clásicos, agente PPO, análisis estadístico y grabación de video.
- **Lo que bloquea:** depurar la geometría en `netedit` y conseguir datos de
  demanda reales. Ambos están detallados en `04` y `06`.

## Lo que sigue

1. Depurar red comunal en `netedit` hasta que `diagnose_net.py` no reporte problemas.
2. Enviar las solicitudes de datos (ver `06`). Cuanto antes, porque los plazos
   legales son de semanas.
3. Decidir si el agente controla las 11 intersecciones del eje o las 43 de la red.
4. Definir los cuatro perfiles de demanda.
5. Entrenamiento en serio y ablation de recompensa.
6. MAPPO con crítico centralizado.
7. Pruebas de robustez.

## El código

Está en `..\tsc-thesis\`. El `README.md` de esa carpeta explica cómo correr todo.
