#!/usr/bin/env python3
# manual

"""
This script runs the simulator headless
"""
import argparse

import gym
import numpy as np
import pyglet
pyglet.options["headless"] = True

from gym_duckietown.envs import DuckietownEnv
from PIL import Image
from cv2 import VideoWriter, VideoWriter_fourcc, cvtColor, COLOR_RGB2BGR

# from experiments.utils import save_img

parser = argparse.ArgumentParser()
parser.add_argument("--map-name", default="udem1")
parser.add_argument("--distortion", default=False, action="store_true")
parser.add_argument("--camera_rand", default=False, action="store_true")
parser.add_argument("--draw-curve", action="store_true", help="draw the lane following curve")
parser.add_argument("--draw-bbox", action="store_true", help="draw collision detection bounding boxes")
parser.add_argument("--domain-rand", action="store_true", help="enable domain randomization")
parser.add_argument("--dynamics_rand", action="store_true", help="enable dynamics randomization")
parser.add_argument("--frame-skip", default=1, type=int, help="number of frames to skip")
parser.add_argument("--seed", default=1, type=int, help="seed")
args = parser.parse_args()

env = DuckietownEnv(
    seed=args.seed,
    map_name=args.map_name,
    draw_curve=args.draw_curve,
    draw_bbox=args.draw_bbox,
    domain_rand=args.domain_rand,
    frame_skip=args.frame_skip,
    distortion=args.distortion,
    camera_rand=args.camera_rand,
    dynamics_rand=args.dynamics_rand,
)

env._load_map("generated")
env.reset()
pixels = env.render("top_down")
im = Image.fromarray(pixels)
im.save("out/start.jpeg")
out = VideoWriter('out/output_video.mp4', VideoWriter_fourcc(*'MP4V'), 30, (800, 600))

while True:
    """
    This function is called at every frame to handle
    movement/stepping and redrawing
    """
    wheel_distance = 0.102
    min_rad = 0.08

    action = np.array([0.44, 0.0])

    v1 = action[0]
    v2 = action[1]
    # Limit radius of curvature
    if v1 == 0 or abs(v2 / v1) > (min_rad + wheel_distance / 2.0) / (min_rad - wheel_distance / 2.0):
        # adjust velocities evenly such that condition is fulfilled
        delta_v = (v2 - v1) / 2 - wheel_distance / (4 * min_rad) * (v1 + v2)
        v1 += delta_v
        v2 -= delta_v

    action[0] = v1
    action[1] = v2

    obs, reward, done, info = env.step(action)
    print("step_count = %s, reward=%.3f" % (env.unwrapped.step_count, reward))

    if done:
        print("done!")
        env.reset()
        break

    pixels = env.render("top_down")
    frame = cvtColor(pixels, COLOR_RGB2BGR)
    out.write(frame)
    # im = Image.fromarray(pixels)
    # im.save("end.jpeg")

out.release()
env.close()