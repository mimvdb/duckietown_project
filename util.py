from duckietown_world import MapFormat1
from gym_duckietown.envs import DuckietownEnv
from PIL import Image
from const import *
from typing import List, Tuple

mock_env = DuckietownEnv(seed=1)

def save_map_image(map_data: MapFormat1, path: str):
    mock_env.map_data = map_data
    mock_env._interpret_map(mock_env.map_data)
    mock_env.reset()
    pixels = mock_env.render("top_down")
    im = Image.fromarray(pixels)
    im.save(path)


def edge_path_to_format(edges: List[Tuple[int, int]]):
    map_dict: MapFormat1 = {}
    map_dict["tile_size"] = TILE_SIZE
    map_dict["tiles"] = graph_transform(edge_path_to_grid(edges))
    map_dict["objects"] = []
    return map_dict


def save_edge_paths(edgess: List[List[Tuple[int, int]]]):
    for i in range(len(edgess)):
        save_map_image(edge_path_to_format(edgess[i]), f"out/map_{i}.jpeg")


def empty() -> List[List[Tuple[int, int, int, int]]]:
    cycle_map = []
    for i in range(HEIGHT):
        # cycle_map.append([(i != 0, True, i != HEIGHT - 1, False)] + [(i != 0, True, i != HEIGHT - 1, True)] * (WIDTH - 2) + [(i != 0, False, i != HEIGHT - 1, True)])
        cycle_map.append([(False, False, False, False)] * WIDTH)
    return cycle_map


def edge_path_to_grid(edges: List[Tuple[int, int]]) -> List[List[Tuple[int, int, int, int]]]:
    c_len = len(edges)
    cycle_map = empty()
    for i in range(c_len):
        neighs = [edges[i - 1], edges[(i + 1) % c_len]]
        x, y = edges[i]
        cycle_map[y][x] = ((x, y - 1) in neighs, (x + 1, y) in neighs, (x, y + 1) in neighs, (x - 1, y) in neighs)
    return cycle_map


def graph_transform(conn_map: List[List[Tuple[int, int, int, int]]]) -> List[List[str]]:
    tile_map = []
    for _ in range(HEIGHT):
        tile_map.append(["grass"] * WIDTH)
    
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if conn_map[y][x] == (False,False,False,False):
                tile_map[y][x] = "grass"
            elif conn_map[y][x] == (False, True, False, True):
                tile_map[y][x] = "straight/E"
            elif conn_map[y][x] == (True, False, True, False):
                tile_map[y][x] = "straight/S"
            elif conn_map[y][x] == (True, True, False, False):
                tile_map[y][x] = "curve_left/S"
            elif conn_map[y][x] == (False, True, True, False):
                tile_map[y][x] = "curve_left/W"
            elif conn_map[y][x] == (False, False, True, True):
                tile_map[y][x] = "curve_left/N"
            elif conn_map[y][x] == (True, False, False, True):
                tile_map[y][x] = "curve_left/E"
            elif conn_map[y][x] == (True, True, True, False):
                tile_map[y][x] = "3way_left/S"
            elif conn_map[y][x] == (False, True, True, True):
                tile_map[y][x] = "3way_left/W"
            elif conn_map[y][x] == (True, False, True, True):
                tile_map[y][x] = "3way_left/N"
            elif conn_map[y][x] == (True, True, False, True):
                tile_map[y][x] = "3way_left/E"
            elif conn_map[y][x] == (True, True, False, True):
                tile_map[y][x] = "4way/E"
            else:
                tile_map[y][x] = ""
                logging.error(f"Unknown tile: {x} {y}")
    return tile_map
