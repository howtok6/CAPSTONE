import numpy as np
from gymnasium import spaces
from sumo_rl.environment.observations import ObservationFunction

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
