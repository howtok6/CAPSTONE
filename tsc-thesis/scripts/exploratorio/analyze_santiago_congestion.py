import WazeRouteCalculator
import time
import csv
import os
from datetime import datetime
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Principales avenidas de Santiago para monitorear
# Formato: "Nombre_Av": {"start": "lat,lon", "end": "lat,lon"}
AVENIDAS_SANTIAGO = {
    "Alameda (Oeste-Este)": {"start": "-33.4500,-70.6800", "end": "-33.4370,-70.6330"},
    "Alameda (Este-Oeste)": {"start": "-33.4370,-70.6330", "end": "-33.4500,-70.6800"},
    "Providencia (Oeste-Este)": {"start": "-33.4350,-70.6300", "end": "-33.4180,-70.6030"},
    "Providencia (Este-Oeste)": {"start": "-33.4180,-70.6030", "end": "-33.4350,-70.6300"},
    "Apoquindo (Oeste-Este)": {"start": "-33.4140,-70.5900", "end": "-33.4100,-70.5700"},
    "Apoquindo (Este-Oeste)": {"start": "-33.4100,-70.5700", "end": "-33.4140,-70.5900"},
    "Vespucio Oriente (Norte-Sur)": {"start": "-33.3800,-70.5900", "end": "-33.4300,-70.5700"},
    "Vespucio Oriente (Sur-Norte)": {"start": "-33.4300,-70.5700", "end": "-33.3800,-70.5900"},
    "Vicuña Mackenna (Norte-Sur)": {"start": "-33.4370,-70.6330", "end": "-33.5000,-70.6100"},
    "Vicuña Mackenna (Sur-Norte)": {"start": "-33.5000,-70.6100", "end": "-33.4370,-70.6330"},
    "La Florida (Norte-Sur)": {"start": "-33.5000,-70.6100", "end": "-33.5500,-70.5800"},
    "La Florida (Sur-Norte)": {"start": "-33.5500,-70.5800", "end": "-33.5000,-70.6100"},
}

CSV_FILE = "data/waze/santiago_congestion_log.csv"

def init_csv():
    os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "avenida", "route_time_mins", "route_distance_km", "avg_speed_kmh", "congestion_index"])

def poll_traffic():
    """Consulta Waze para todas las avenidas definidas y guarda los datos."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    region = 'EU' # ROW (Rest of World)
    
    records = []
    for nombre, coords in AVENIDAS_SANTIAGO.items():
        try:
            route = WazeRouteCalculator.WazeRouteCalculator(coords["start"], coords["end"], region)
            route_time, route_distance = route.calc_route_info(real_time=True)
            
            # Velocidad promedio = Distancia / Tiempo
            avg_speed = route_distance / (route_time / 60) if route_time > 0 else 0
            
            # Indice de congestión (Proxy): Velocidad libre estimada (50 km/h) / Velocidad actual
            # Valores > 1 indican congestión. Valores > 2 indican mucho tráfico (velocidad a la mitad).
            free_flow_speed = 50.0 
            congestion_index = free_flow_speed / avg_speed if avg_speed > 0 else 0
            
            records.append([timestamp, nombre, route_time, route_distance, round(avg_speed, 2), round(congestion_index, 2)])
            logging.info(f"[{nombre}] Vel: {avg_speed:.1f} km/h | Índice Congestión: {congestion_index:.2f}")
            
        except Exception as e:
            logging.error(f"Error consultando {nombre}: {e}")
            
    # Guardar en CSV
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(records)

def generate_report():
    """Lee el CSV histórico y genera un reporte de las avenidas más congestionadas."""
    if not os.path.exists(CSV_FILE):
        logging.warning("No hay datos suficientes para el reporte.")
        return
        
    df = pd.read_csv(CSV_FILE)
    if df.empty: return
    
    # Agrupar por avenida y calcular el índice de congestión promedio
    report = df.groupby("avenida").agg(
        avg_speed_promedio=("avg_speed_kmh", "mean"),
        congestion_index_promedio=("congestion_index", "mean"),
        muestras=("timestamp", "count")
    ).reset_index()
    
    report = report.sort_values(by="congestion_index_promedio", ascending=False)
    
    print("\n" + "="*50)
    print("REPORTE DE AVENIDAS MÁS CONGESTIONADAS DE SANTIAGO")
    print("="*50)
    print(report.to_string(index=False))
    print("="*50 + "\n")

if __name__ == "__main__":
    init_csv()
    
    # Modo de prueba: Tomar una muestra inmediatamente y generar el reporte
    print("Recolectando muestra inicial...")
    poll_traffic()
    generate_report()
    
    print("\nPara monitorear durante el día, puedes ejecutar un loop:")
    print("while True:")
    print("    poll_traffic()")
    print("    time.sleep(900) # 15 minutos")
