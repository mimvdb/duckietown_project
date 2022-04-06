#!/usr/bin/env python3
import argparse
import yaml
import logging
import os
from random import Random
from duckietown_world import MapFormat1

import networkx as nx

from typing import List, Tuple
from const import *

parser = argparse.ArgumentParser()
parser.add_argument("--force", action="store_true", help="overwrite existing maps")
parser.add_argument("--width", default=5, help="width of the map to generate")
parser.add_argument("--height", default=5, help="height of the map to generate")
parser.add_argument("--seed", default=None, help="seed for random generator")
parser.add_argument("--file-name", default="generated.yaml")
args = parser.parse_args()

rand = Random()



def save_map(map_path: str, map_data: MapFormat1):
    assert map_path.endswith(".yaml")
    if os.path.exists(map_path) and os.path.isfile(map_path):
        logging.warning("Map already exists")
        if not args.force:
            logging.warning("Skipping")
            return
    logging.debug(f"Writing map to {map_path}")

    with open(map_path, "w") as f:
        yaml.dump(map_data, f, default_flow_style=None)

# def neighs(x: int, y: int):
#     return [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]

# def is_set(l: List[List[bool]], x: int, y: int) -> bool:
#     if x < 0 or y < 0 or x >= args.width or y >= args.height:
#         return False
#     else:
#         return l[y][x]

# def gen_cycle() -> List[List[bool]]:
#     cycle_map = []
#     for i in range(args.height):
#         cycle_map.append([False] * args.width)
#     prevX = rand.randrange(args.width)
#     prevY = rand.randrange(args.height)
#     track = [(prevX, prevY)]
#     visited = {(prevX, prevY)}
#     cycle_map[prevY][prevX] = True

#     while (sum([i in visited for i in neighs(prevX, prevY)]) < 2):
#         x, y = rand.choice(neighs(prevX, prevY))
#         if x < 0 or y < 0 or x >= args.width or y >= args.height or len(track) > 1 and(x, y) == track[-2]:
#             continue
#         track.append((x, y))
#         visited.add((x, y))
#         cycle_map[y][x] = True
#         prevX, prevY = x, y
    
#     for x, y in neighs(prevX, prevY):
#         if (x, y) in visited and (x, y) not in track[-2:]:
#             for revX, revY in track[:track.index((x, y))]:
#                 cycle_map[revY][revX] = False

#     return cycle_map

# def gen_cycle2() -> List[List[bool]]:
#     cycle_map = []
#     for i in range(args.height):
#         cycle_map.append([False] * args.width)
#     prevX = rand.randrange(args.width)
#     prevY = rand.randrange(args.height)
#     candidates = {(prevX, prevY)}
#     cycle_map[prevY][prevX] = True

#     while candidates:
#         prevX, prevY = candidates.pop()
#         if (sum([is_set(cycle_map, xz, yz) for xz, yz in neighs(prevX, prevY)]) < 2):
#             x, y = rand.choice(neighs(prevX, prevY))
#             if x < 0 or y < 0 or x >= args.width or y >= args.height:
#                 candidates.add((prevX, prevY))
#                 continue
#             candidates.add((x, y))
#             cycle_map[y][x] = True
#         if (sum([is_set(cycle_map, xz, yz) for xz, yz in neighs(prevX, prevY)]) < 2):
#             candidates.add((prevX, prevY))


#     return cycle_map

# def full() -> List[List[Tuple[int, int, int, int]]]:
#     cycle_map = []
#     for i in range(args.height):
#         cycle_map.append([(i != 0, True, i != args.height - 1, False)] + [(i != 0, True, i != args.height - 1, True)] * (args.width - 2) + [(i != 0, False, i != args.height - 1, True)])
#     return cycle_map

def all_loops() -> List[List[Tuple[int, int]]]:
    grid = nx.grid_2d_graph(args.width, args.height, create_using=nx.DiGraph)
    # Not uniform over same shape cycles, for example there are lots of 2x2 cycles.
    # Furthermore, they are directed, so all undirected cycles appear twice
    # (unsure if different starting points count as distinct cycles, assuming not)
    return list(nx.simple_cycles(grid))

def flatten_idx(x: Tuple[int, int]):
    return x[0] * args.height + x[1]

def normalize_cycle(sequence: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """
    Translate the cycle to the corner, rotate the sequence it so it starts with the lowest index, and reverse so the next is higher than the previous

    Normalizing the rotation with respect to the map itself remains to be done
    """
    low_x = min(map(lambda x: x[0], sequence))
    low_y = min(map(lambda x: x[1], sequence))
    min_idx = sequence.index(min(sequence, key=flatten_idx))
    rotated = sequence[min_idx:] + sequence[:min_idx]
    if flatten_idx(rotated[-1]) > flatten_idx(rotated[1]):
        rotated.reverse()
        rotated = rotated[-1:] + rotated[:-1]


    return list(map(lambda x: (x[0] - low_x, x[1] - low_y), rotated))

def filter_cycles(sequence: List[Tuple[int, int]]) -> bool:
    seq_len = len(sequence)
    return 4 <= seq_len <= 10

# def distance_measure(sol1: List[Tuple[int, int]], sol2: List[Tuple[int, int]]): 

def check(bool_map: List[List[bool]], x: int, y: int, n: int, e: int, s: int, w: int) -> bool:
    ee = bool_map[y][x + 1] if x + 1 < args.width else 0
    ww = bool_map[y][x - 1] if x - 1 >= 0 else 0
    ss = bool_map[y + 1][x] if y + 1 < args.height else 0
    nn = bool_map[y - 1][x] if y - 1 >= 0 else 0
    return ee == e and ww == w and nn == n and ss == s

def map_transform(bool_map: List[List[bool]]) -> List[List[str]]:
    tile_map = []
    for i in range(args.height):
        tile_map.append(["grass"] * args.width)
    
    for y in range(args.height):
        for x in range(args.width):
            if bool_map[y][x]:
                if check(bool_map, x, y, 0, 1, 0, 1):
                    tile_map[y][x] = "straight/E"
                elif check(bool_map, x, y, 1, 0, 1, 0):
                    tile_map[y][x] = "straight/S"
                elif check(bool_map, x, y, 1, 1, 0, 0):
                    tile_map[y][x] = "curve_left/S"
                elif check(bool_map, x, y, 0, 1, 1, 0):
                    tile_map[y][x] = "curve_left/W"
                elif check(bool_map, x, y, 0, 0, 1, 1):
                    tile_map[y][x] = "curve_left/N"
                elif check(bool_map, x, y, 1, 0, 0, 1):
                    tile_map[y][x] = "curve_left/E"
                elif check(bool_map, x, y, 1, 1, 1, 0):
                    tile_map[y][x] = "3way_left/S"
                elif check(bool_map, x, y, 0, 1, 1, 1):
                    tile_map[y][x] = "3way_left/W"
                elif check(bool_map, x, y, 1, 0, 1, 1):
                    tile_map[y][x] = "3way_left/N"
                elif check(bool_map, x, y, 1, 1, 0, 1):
                    tile_map[y][x] = "3way_left/E"
                elif check(bool_map, x, y, 1, 1, 0, 1):
                    tile_map[y][x] = "4way/E"
                else:
                    tile_map[y][x] = ""
                    logging.error(f"Unknown tile: {x} {y}")
    return tile_map

def object_placement(n: int, min_dist: float, possible_tiles: List[Tuple[int, int]]) -> List[Tuple[float, float]]:
    ducks = []
    min_dist_sq = min_dist * min_dist
    for _ in range(n):
        for _ in range(50): # Max tries
            # TODO verify these tile size calcs
            xoff = rand.random() * TILE_SIZE
            yoff = rand.random() * TILE_SIZE
            startX, startY = rand.choice(possible_tiles)
            x, y = startX * TILE_SIZE + xoff, startY * TILE_SIZE + yoff
            if (all(map(lambda o: (x-o[0])**2 + (y-o[1])**2 > min_dist_sq, ducks))):
                ducks.append((x, y))
                break
    return ducks

def placements_to_ducks(placements: List[Tuple[float, float]]) -> List:
    return list(map(lambda x: {
        "height": 0.06,
        "kind": "duckie",
        "optional": False,
        "pos": [x[0], x[1]],
        "rotate": rand.randrange(0, 360),
        "static": True
    }, placements))

def gen_map():
    choices = all_loops()
    logging.warning(f"All loops generated {len(choices)} possibilities")
    choices = list(filter(filter_cycles, choices))
    logging.warning(f"Filtered generated {len(choices)} possibilities")
    choices = list(map(list,set(map(tuple, map(normalize_cycle, choices)))))
    logging.warning(f"Normalization generated {len(choices)} possibilities")

    from util import save_edge_paths, edge_path_to_format
    save_edge_paths(choices)

    edges = rand.choice(choices)
    map_dict = edge_path_to_format(edges)
    map_dict["objects"] = placements_to_ducks(object_placement(5, 2, edges))
    return map_dict

the_map = gen_map()
save_map(args.file_name, the_map)