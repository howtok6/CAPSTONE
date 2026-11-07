import numpy as np
from gymnasium import spaces
from sumo_rl.environment.observations import ObservationFunction

# Fases verdes del cruce más complejo del eje comunal. Debe cubrir todos los
# semáforos controlados: `PhaseObservation` falla si encuentra uno con más.
MAX_FASES = 4


class PhaseObservation(ObservationFunction):
    """Observación del mismo tamaño y significado en todos los cruces.

    La de sumo-rl trae una columna por pista: en el eje hay cruces de 4 a 23
    pistas, y al rellenar con ceros la misma columna es densidad en un cruce y
    cola en otro. Con parámetros compartidos, la red no puede aprender eso bien.

    Aquí cada salida i de la red tiene sus columnas: lo que pasaría si diera
    verde a la fase i. Por fase: densidad y cola medias de las pistas que
    atiende, y densidad de las pistas a las que descarga (para no soltar
    vehículos sobre una salida llena).

    [fase actual (4), fases que existen (4), puede cambiar, tiempo de verde,
     densidad entrada (4), cola entrada (4), densidad salida (4)]  = 22 columnas
    """

    DIM = 2 * MAX_FASES + 2 + 3 * MAX_FASES

    def __init__(self, ts):
        super().__init__(ts)
        self._por_fase = None

    def _preparar(self):
        ts = self.ts
        if ts.num_green_phases > MAX_FASES:
            raise ValueError(f"{ts.id} tiene {ts.num_green_phases} fases; sube MAX_FASES")
        enlaces = ts.sumo.trafficlight.getControlledLinks(ts.id)
        self._por_fase = []
        for fase in ts.green_phases:
            ent, sal = set(), set()
            for i, senal in enumerate(fase.state):
                if senal in "Gg" and i < len(enlaces) and enlaces[i]:
                    ent.add(enlaces[i][0][0])
                    sal.add(enlaces[i][0][1])
            self._por_fase.append((sorted(ent), sorted(sal)))

    def __call__(self):
        ts = self.ts
        if self._por_fase is None:
            self._preparar()
        densidad = dict(zip(ts.lanes, ts.get_lanes_density()))
        cola = dict(zip(ts.lanes, ts.get_lanes_queue()))
        salida = dict(zip(ts.out_lanes, ts.get_out_lanes_density()))

        o = np.zeros(self.DIM, dtype=np.float32)
        o[ts.green_phase] = 1.0
        o[MAX_FASES:MAX_FASES + ts.num_green_phases] = 1.0
        o[2 * MAX_FASES] = float(ts.time_since_last_phase_change >= ts.min_green + ts.yellow_time)
        o[2 * MAX_FASES + 1] = min(1.0, ts.time_since_last_phase_change / (ts.max_green + ts.yellow_time))
        base = 2 * MAX_FASES + 2
        for i, (ent, sal) in enumerate(self._por_fase):
            if ent:
                o[base + i] = sum(densidad[p] for p in ent) / len(ent)
                o[base + MAX_FASES + i] = sum(cola[p] for p in ent) / len(ent)
            if sal:
                o[base + 2 * MAX_FASES + i] = sum(salida[p] for p in sal) / len(sal)
        return o

    def observation_space(self):
        return spaces.Box(low=0.0, high=1.0, shape=(self.DIM,), dtype=np.float32)


class WazeCongestionObservation(ObservationFunction):
    """
    Extiende la observación por defecto de sumo-rl añadiendo un factor de 
    'congestión global' que representa los datos extraídos de Waze.
    
    En el entrenamiento (simulación), este factor se aproxima calculando
    la densidad/demora extendida más allá de los carriles adyacentes, 
    o utilizando la presión como proxy de congestión en ruta.
    """
    def __init__(self, ts):
        super().__init__(ts)

    def __call__(self):
        # 1. Observación clásica (fase actual, green_min, densidad, colas)
        phase_id = [1 if self.ts.green_phase == i else 0 for i in range(self.ts.num_green_phases)]
        min_green = [0 if self.ts.time_since_last_phase_change < self.ts.min_green + self.ts.yellow_time else 1]
        density = self.ts.get_lanes_density()
        queue = self.ts.get_lanes_queue()

        # 2. Factor Waze: "Congestión de la Ruta"
        # En la realidad esto vendría del API (ej. avg_speed_kmh).
        # En simulación, usamos un proxy: la suma de tiempos de espera 
        # dividida por una constante, o la presión de la intersección.
        # Aquí añadimos la presión (diferencia de vehículos entre entrada y salida)
        # y el tiempo de espera acumulado (normalizado).
        pressure = self.ts.get_pressure()
        
        # Opcional: obtener waiting time (en sumo-rl get_accumulated_waiting_time_per_lane)
        wait_times = self.ts.get_accumulated_waiting_time_per_lane()
        avg_wait = sum(wait_times) / max(1, len(wait_times))
        
        # Agregamos las variables exógenas simuladas al final de la observación
        waze_proxy = [
            pressure / 10.0,  # normalización arbitraria
            avg_wait / 100.0
        ]

        obs = np.array(phase_id + min_green + density + queue + waze_proxy, dtype=np.float32)
        return obs

    def observation_space(self):
        # Fases + min_green_flag + (densidad por carril) + (cola por carril) + (2 variables Waze)
        shape = self.ts.num_green_phases + 1 + 2 * len(self.ts.lanes) + 2
        return spaces.Box(low=-np.inf, high=np.inf, shape=(shape,), dtype=np.float32)
