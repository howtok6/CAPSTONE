# Windows nativo vs WSL2 — decisión corregida (24-ago-2026)

## Corrección importante

La recomendación anterior (23-ago) decía que `libsumo` «es problemático» en
Windows y que quedarías con TraCI y entrenamientos ~8× más lentos. **Era
falso.** Se afirmó desde conocimiento general en vez de comprobarlo, y era el
argumento principal para descartar Windows.

## Lo que se verificó

Consulta directa a PyPI para `win_amd64` / Python 3.12: **todos** los paquetes
del proyecto tienen rueda nativa de Windows, incluido
`libsumo-1.27.1-cp312-cp312-win_amd64.whl`. También `torch` y `ray`.

Evidencia adicional de la máquina de Gabriel: en
`C:\Users\Gabriel\Desktop\TESIS\tsc-thesis` hay un `.pytest_cache` con los 5
tests recogidos y **sin archivo `lastfailed`** — pytest solo lo escribe cuando
algo falla. Es decir, la batería ya pasó en Windows, incluido
`test_maxpressure_beats_fixed_time`, que requiere que SUMO simule de verdad.

## Diferencias que sí existen

| Diferencia | Impacto | Cuándo aparece |
|---|---|---|
| **Ray en beta en Windows** (doc oficial) | Real | Solo en la fase MAPPO/CTDE, mes 5 |
| **Windows no tiene `fork()`** — Python usa `spawn`, cada worker reimporta el módulo | Molestia | Al subir `--n-cpus`. Los scripts ya traen guarda `if __name__ == "__main__":` |
| **No hay `make`** | Menor | Correr scripts directo o `winget install ezwinports.make` |
| **Entorno de referencia** — papers y benchmarks son Linux | Menor | Al buscar ayuda cuando algo falle |
| **Docker al cierre** usa WSL2 por debajo igual | Menor | Solo si se publica imagen reproducible |

## Ventajas de Windows nativo

- `netedit` y `sumo-gui` nativos — mejor que WSLg, y va a pasar semanas en
  netedit depurando geometría.
- Una capa menos que depurar, con presupuesto de ~10 h/semana.
- Sin el castigo de rendimiento de `/mnt/c`.
- Ya lo tiene andando: SUMO instalado, escenario abierto, repo en el escritorio,
  tests pasando.

## Recomendación vigente

**Empezar en Windows nativo.** Los meses 1–4 (escenario, netedit, calibración,
baselines, IPPO con Stable-Baselines3) no tocan nada de lo que Windows hace
peor. Migrar después es barato: el código no tiene supuestos POSIX (todas las
rutas usan `os.path.join`, ningún `shell=True`, guardas `__main__` en todos los
scripts), el venv es desechable y el repo es portable.

Si Ray da problemas en el mes 5, se monta WSL2 esa semana. El runbook de WSL2
sigue vigente: https://claude.ai/code/artifact/1db8e56b-b387-4bf7-9cb1-5a1bb9c27fe0

## Cambios al repositorio

- `--n-cpus` por defecto pasó de 2 a **1** en `train_rl.py`. Es más seguro en
  ambas plataformas: con 2 hubo un cuelgue de arranque incluso en Linux.
- README con sección «Windows nativo o WSL2».
- Archivos actualizados directamente en
  `C:\Users\Gabriel\Desktop\TESIS\tsc-thesis`: `requirements.txt`,
  `scripts/train_rl.py`, `README.md`.

## Pendiente de medir

No se comparó la velocidad real de simulación entre Windows nativo y WSL2 en su
máquina. Es medible con el propio `run_baselines.py` cronometrado en ambos, si
alguna vez importa.
