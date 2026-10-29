import WazeRouteCalculator
import json
import time
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Definir tramos de interés en Santiago (Providencia/Las Condes)
# Formato: "latitud,longitud"
TRAMOS = {
    "Apoquindo_Oeste_Este": {
        "start": "-33.4140,-70.5900", # Tobalaba
        "end": "-33.4100,-70.5700"    # Escuela Militar
    },
    "Providencia_Este_Oeste": {
        "start": "-33.4180,-70.6030", # Los Leones
        "end": "-33.4350,-70.6300"    # Plaza Italia
    }
}

def fetch_congestion_data():
    """
    Usa WazeRouteCalculator para estimar el tiempo de viaje y la distancia,
    lo que sirve como un proxy en tiempo real para medir la congestión.
    """
    region = 'EU' # ROW (Rest of World)
    results = {}
    
    for nombre_tramo, coords in TRAMOS.items():
        try:
            logging.info(f"Consultando tramo: {nombre_tramo}")
            # route_time (minutos), route_distance (km)
            route = WazeRouteCalculator.WazeRouteCalculator(coords["start"], coords["end"], region)
            route_time, route_distance = route.calc_route_info(real_time=True)
            
            # Calculamos la velocidad promedio como indicador de congestión (km/h)
            velocidad_promedio = route_distance / (route_time / 60) if route_time > 0 else 0
            
            results[nombre_tramo] = {
                "start_coords": coords["start"],
                "end_coords": coords["end"],
                "route_time_mins": route_time,
                "route_distance_km": route_distance,
                "avg_speed_kmh": round(velocidad_promedio, 2)
            }
            
            logging.info(f" - Distancia: {route_distance} km, Tiempo: {route_time} mins, Vel. Promedio: {velocidad_promedio:.2f} km/h")
            
        except Exception as e:
            logging.error(f"Error consultando tramo {nombre_tramo}: {e}")
            
    return {
        "timestamp": time.time(),
        "rutas": results
    }

if __name__ == "__main__":
    data = fetch_congestion_data()
    if data:
        filename = f"data/waze/congestiones_waze_{int(data['timestamp'])}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info(f"Datos guardados exitosamente en {filename}")
