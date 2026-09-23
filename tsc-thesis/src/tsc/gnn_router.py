import torch
import torch.nn.functional as F
try:
    from torch_geometric.nn import GCNConv
except ImportError:
    print("Advertencia: torch-geometric no está instalado.")
import xml.etree.ElementTree as ET

class CongestionGNN(torch.nn.Module):
    """
    Graph Convolutional Network (GCN) para predecir costos dinámicos de enrutamiento
    basados en la congestión de la red vehicular.
    """
    def __init__(self, num_node_features, hidden_channels):
        super(CongestionGNN, self).__init__()
        # Capas de convolución de grafos
        self.conv1 = GCNConv(num_node_features, hidden_channels)
        self.conv2 = GCNConv(hidden_channels, hidden_channels)
        # Regresor lineal para predecir el "costo" o "demora extra" del nodo
        self.regressor = torch.nn.Linear(hidden_channels, 1)

    def forward(self, x, edge_index):
        # Propagación del mensaje por la red de calles
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = self.conv2(x, edge_index)
        x = F.relu(x)
        
        # Predicción del costo (asegurando valores positivos)
        cost = self.regressor(x)
        return F.softplus(cost)

class GNNRouter:
    """
    Envoltorio que integra la red neuronal de grafos con la simulación SUMO.
    Interpreta el archivo net.xml para construir el grafo y actualiza los pesos de TraCI.
    """
    def __init__(self, net_file: str):
        self.net_file = net_file
        self.edge_index = None
        self.node_ids = []
        self.edge_ids = []
        
        # Features: [densidad_promedio, cola_promedio, velocidad_promedio]
        self.model = CongestionGNN(num_node_features=3, hidden_channels=16) 
        self._build_graph()
        
    def _build_graph(self):
        """Parsea la red de SUMO para extraer nodos (intersecciones) y aristas (calles)."""
        tree = ET.parse(self.net_file)
        root = tree.getroot()
        
        junction_map = {}
        for idx, junction in enumerate(root.findall('junction')):
            jid = junction.get('id')
            if jid.startswith(':'):  # Ignorar uniones internas de SUMO
                continue
            junction_map[jid] = idx
            self.node_ids.append(jid)
            
        sources, targets = [], []
        
        for edge in root.findall('edge'):
            eid = edge.get('id')
            if 'function' in edge.attrib and edge.attrib['function'] == 'internal':
                continue
                
            u = edge.get('from')
            v = edge.get('to')
            if u in junction_map and v in junction_map:
                sources.append(junction_map[u])
                targets.append(junction_map[v])
                self.edge_ids.append(eid)
                
        self.edge_index = torch.tensor([sources, targets], dtype=torch.long)
        
    def get_node_features(self, sim):
        """Extrae el estado actual de la red de SUMO (densidad, colas) para la GNN."""
        x = []
        for jid in self.node_ids:
            # TODO: En una implementación completa, aquí consultamos a sim.conn (TraCI)
            # por el estado real de los edges entrantes a 'jid'.
            # Para el esqueleto, enviamos features simulados.
            x.append([0.5, 10.0, 15.0]) # [densidad, cola, velocidad]
        return torch.tensor(x, dtype=torch.float)

    def act(self, sim):
        """
        Paso de inferencia:
        1. Obtiene las features (estado del tráfico).
        2. La GNN predice el costo de cada nodo.
        3. Se inyecta el nuevo costo en TraCI para que los vehículos cambien de ruta.
        """
        x_tensor = self.get_node_features(sim)
        
        with torch.no_grad():
            predicted_costs = self.model(x_tensor, self.edge_index)
        
        # Actualizar los pesos de ruteo de SUMO (Adaptation Time)
        for i, eid in enumerate(self.edge_ids):
            target_node_idx = self.edge_index[1][i].item()
            # El costo extra predicho por la GNN se suma al tiempo de viaje
            gnn_cost_penalty = predicted_costs[target_node_idx].item()
            
            try:
                # Obtenemos el tiempo base de recorrer la calle
                base_time = sim.conn.edge.getTraveltime(eid)
                # Forzamos a TraCI a usar este nuevo "tiempo de viaje" modificado por la GNN
                # para que cuando hagamos rerouteTraveltime(), los vehículos lo eviten.
                sim.conn.edge.setAdaptationTime(eid, base_time + (gnn_cost_penalty * 10))
            except Exception:
                pass
