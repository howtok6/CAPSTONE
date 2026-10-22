"""Script para evaluar el impacto de simular desvíos tipo Waze."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from tsc.runner import run_episode
from tsc.controllers.fixed import FixedTimeController

def main():
    net = "scenarios/alameda_providencia/net.net.xml"
    rou = "scenarios/alameda_providencia/routes.rou.xml"
    
    # Comprobar que los archivos existen
    if not os.path.exists(net):
        print(f"Error: No existe el archivo {net}. Debes correr 'python scripts/build_grid.py' antes.")
        return
        
    print("--- 1. Evaluando sin enrutamiento Waze ---")
    res_no_waze = run_episode(
        controller=FixedTimeController(),
        net_file=net,
        route_file=rou,
        seed=42,
        waze_rerouting_threshold=-1.0 # Desactivado
    )
    
    print("\n--- 2. Evaluando CON enrutamiento Waze (Desvío Estándar) ---")
    res_waze = run_episode(
        controller=FixedTimeController(),
        net_file=net,
        route_file=rou,
        seed=42,
        waze_rerouting_threshold=500.0, 
        waze_reroute_pct=0.2 
    )

    print("\n--- 3. Evaluando CON Graph Neural Networks (GNN) Router ---")
    res_gnn = run_episode(
        controller=FixedTimeController(),
        net_file=net,
        route_file=rou,
        seed=42,
        waze_rerouting_threshold=500.0, 
        waze_reroute_pct=0.2,
        use_gnn_router=True
    )
    
    print("\n================ RESULTADOS ================")
    print(f"Demora Media (sin Waze): {res_no_waze.get('time_loss_mean', 0):.2f} s")
    print(f"Demora Media (con Waze): {res_waze.get('time_loss_mean', 0):.2f} s")
    print(f"Demora Media (con GNN):  {res_gnn.get('time_loss_mean', 0):.2f} s")
    
    print(f"\nThroughput (sin Waze): {res_no_waze.get('throughput', 0):.2f} veh/h")
    print(f"Throughput (con Waze): {res_waze.get('throughput', 0):.2f} veh/h")
    print(f"Throughput (con GNN):  {res_gnn.get('throughput', 0):.2f} veh/h")
    
    diff_delay = ((res_waze.get('time_loss_mean', 1) / max(1e-5, res_no_waze.get('time_loss_mean', 1))) - 1) * 100
    print(f"\nVariación en demora (Waze vs Base): {diff_delay:+.1f}%")

if __name__ == "__main__":
    main()
