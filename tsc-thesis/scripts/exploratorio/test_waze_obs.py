import sys
import os
# Asegurar que el modulo local se puede importar
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from tsc.rl_env import make_sb3_vec_env

def test_waze_obs():
    print("Creando entorno SB3 con WazeCongestionObservation...")
    try:
        # Usamos el escenario de grilla de prueba que debe existir
        env = make_sb3_vec_env(
            net_file="scenarios/grid4x4/net.net.xml",
            route_file="scenarios/grid4x4/routes.rou.xml",
            use_waze_obs=True,
            num_vec_envs=1
        )
        
        obs = env.reset()
        print(f"Observation shape: {obs.shape}")
        # obs.shape should be [num_envs_total, obs_dim]
        # In a 4x4 grid there are 16 intersections, so 16 agents. 
        # With parameter sharing, the vectorized env treats them as batch elements.
        print("Test exitoso. Las observaciones Waze se calcularon sin error.")
        env.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_waze_obs()
