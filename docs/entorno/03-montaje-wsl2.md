# Montaje del entorno en WSL2 — paso a paso

Runbook publicado el 24-ago-2026.
Página completa: https://claude.ai/code/artifact/1db8e56b-b387-4bf7-9cb1-5a1bb9c27fe0

> **Nota (24-ago):** la decisión vigente es trabajar en **Windows nativo**
> (ver `02-windows-vs-wsl2.md`). Este runbook queda como plan B, principalmente
> para la fase de MAPPO si Ray da problemas en Windows.

**Qué está verificado:** todo el lado Linux se ejecutó en Ubuntu 24.04 —
instalación limpia desde `requirements.txt` en un venv nuevo, `make grid` y
`make test`— con Python 3.11 y 3.12; las 5 pruebas pasan en ambos. Los pasos de
Windows (WSL2, WSLg, driver NVIDIA) siguen documentación oficial de Microsoft
y NVIDIA: no hubo acceso a la máquina de Gabriel para ejecutarlos.

## Parte A — Windows

1. **Virtualización activa.** Administrador de tareas → Rendimiento → CPU debe
   decir «Virtualización: Habilitada». Si no, activar `VT-x`/`AMD-V`/`SVM` en
   la BIOS. Sin esto el paso 2 falla con un error que no lo menciona.
2. **`wsl --install -d Ubuntu-24.04`** en PowerShell como administrador.
   Reiniciar aunque no lo pida. Crear usuario y contraseña de Linux (la
   contraseña no se muestra al escribirla).
   *Verificación:* `wsl -l -v` → `Ubuntu-24.04` con `VERSION 2`. Si sale 1:
   `wsl --set-version Ubuntu-24.04 2`.
3. **`wsl --update`** — trae WSLg, que permite abrir `sumo-gui` y `netedit`
   como ventanas de Windows.

## Parte B — Ubuntu

4. **Dependencias:**
   `sudo apt install -y python3-venv python3-pip git build-essential libgl1 libglx-mesa0 libxext6 libxrender1 libexpat1 unzip`
   Las cinco bibliotecas gráficas son las que enlaza `sumo-gui` (verificado con
   `ldd`); la imagen de Ubuntu para WSL viene mínima y no las trae. Si falta
   alguna, el binario nombra el archivo exacto: `apt-file search` y se instala.
5. **Repositorio en `~/tesis`, NUNCA en `/mnt/c/…`.** Cruzar la frontera
   Windows↔Linux en cada lectura hace la simulación varias veces más lenta, y
   se corren miles de episodios.
6. **venv + `pip install -r requirements.txt`.** SUMO viene en el paquete
   `eclipse-sumo` de PyPI, binarios incluidos: no hay que instalarlo aparte en
   Ubuntu. El de Windows sigue sirviendo para mirar redes desde allá.
   *Verificación:* `python -c "import sumo, sumo_rl, stable_baselines3; print('ok')"`.
7. **`make grid` y `make test`.** *Verificación clave:* `5 passed`. Confirma
   que SUMO corre, que las fases se leen bien, que Webster calcula y que
   Max-Pressure le gana al tiempo fijo.
8. **`sumo-gui -c scenarios/apoquindo/apoquindo.sumocfg`.** La ventana aparece
   en el escritorio de Windows vía WSLg.

## Parte C — Opcionales

9. **GPU:** `nvidia-smi` dentro de Ubuntu debe listar la tarjeta sin instalar
   nada. Luego `pip install torch --index-url https://download.pytorch.org/whl/cu124`.
   **NUNCA instalar el driver NVIDIA de Linux dentro de WSL** — la doc de NVIDIA
   es explícita: el driver de Windows es el único, y se mapea solo. Si se
   instala CUDA Toolkit, usar la variante *WSL-Ubuntu* y el paquete
   `cuda-toolkit-12-x`, nunca los metapaquetes `cuda` o `cuda-drivers`.
   Requiere driver R495 o posterior.
10. **VS Code** en Windows + extensión WSL; luego `code .` desde Ubuntu.

## Modos de falla frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `wsl --install` falla | Virtualización off en BIOS | Paso 1 |
| `VERSION 1` en `wsl -l -v` | Distro en WSL1 | `wsl --set-version Ubuntu-24.04 2` |
| Todo lento | Repo en `/mnt/c/…` | Mover a `~/tesis` |
| `command not found: make` | Falta `build-essential` | Paso 4 |
| `ensurepip is not available` | Falta `python3-venv` | Paso 4 |
| `ModuleNotFoundError` | venv no activado | `source .venv/bin/activate` |
| `error while loading shared libraries` | Falta biblioteca gráfica | El mensaje la nombra |
| GUI sin ventana | WSLg desactualizado | `wsl --update` + `wsl --shutdown` |
| Script con GUI colgado sin error | Falta `--quit-on-end true` | Ya resuelto en `record_run.py` |
| `nvidia-smi: command not found` | Driver Windows < R495 | Actualizar en Windows |

## Rutina diaria

```
cd ~/tesis/tsc-thesis && source .venv/bin/activate
make diagnose  SCENARIO=scenarios/apoquindo
make baselines SCENARIO=scenarios/apoquindo
make compare   SCENARIO=scenarios/apoquindo
make video     SCENARIO=scenarios/apoquindo
```
