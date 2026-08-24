SCENARIO ?= scenarios/grid4x4
SEEDS    ?= 10
STEPS    ?= 200000

.PHONY: help setup grid webster baselines train eval compare test clean

help:
	@echo "make grid       - genera el escenario sintético 4x4"
	@echo "make webster    - calcula el plan de Webster del escenario"
	@echo "make baselines  - evalúa los controladores clásicos"
	@echo "make train      - entrena el agente PPO (parameter sharing)"
	@echo "make eval       - evalúa la política entrenada"
	@echo "make compare    - análisis estadístico de los resultados"
	@echo "make test       - pruebas rápidas del pipeline"
	@echo ""
	@echo "Variables: SCENARIO=$(SCENARIO) SEEDS=$(SEEDS) STEPS=$(STEPS)"

setup:
	pip install -r requirements.txt

grid:
	python scripts/build_grid.py --size 4 --out scenarios/grid4x4

webster:
	python scripts/build_webster.py --scenario $(SCENARIO)

baselines:
	python scripts/run_baselines.py --scenario $(SCENARIO) --seeds $(SEEDS)

train:
	python scripts/train_rl.py --scenario $(SCENARIO) --steps $(STEPS)

eval:
	python scripts/eval_rl.py --scenario $(SCENARIO) \
		--model models/$(notdir $(SCENARIO))/ppo_wait.zip --seeds $(SEEDS)

compare:
	python scripts/compare.py --results results/$(notdir $(SCENARIO))_baselines.json

test:
	python -m pytest tests -q

all: grid webster baselines train eval compare

clean:
	rm -rf results/*.json models/* __pycache__ src/tsc/__pycache__

diagnose:
	python scripts/diagnose_net.py --scenario $(SCENARIO)

apoquindo:
	python scripts/build_santiago.py \
		--bbox -70.5950,-33.4200,-70.5650,-33.4080 \
		--keep-geo-boundary -70.59569,-33.41789,-70.56457,-33.40687 \
		--out scenarios/apoquindo --period 0.7

video:
	xvfb-run -a -s "-screen 0 1600x900x24" python scripts/record_run.py \
		--scenario $(SCENARIO) --controller maxpressure \
		--begin 900 --seconds 300 --zoom 750 --center 1200,900

gui:
	sumo-gui -c $(SCENARIO)/$(notdir $(SCENARIO)).sumocfg
