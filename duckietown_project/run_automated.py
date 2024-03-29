# Connects to a running simulator and bot image, and connects them together and evaluates them.
# Adapted from duckietown_experiment_manager

import logging

from aido_analyze.utils_video import make_video_ui_image
logging.basicConfig(level=logging.DEBUG)
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import functools
from aido_schemas.protocol_simulator import FriendlyPose, FriendlyVelocity, RobotConfiguration, ScenarioRobotSpec
import duckietown_challenges as dc
import asyncio
import os
import traceback
import shutil

from typing import cast, Dict, Iterator, List, Optional, Set

from aido_analyze.utils_drawing import read_and_draw
from aido_schemas import (
    DB20ObservationsOnlyState,
    DB20ObservationsPlusState,
    DB20ObservationsWithTimestamp,
    DTSimStateDump,
    DumpState,
    EpisodeStart,
    GetCommands,
    GetDuckieState,
    GetRobotObservations,
    GetRobotState,
    JPGImage,
    protocol_agent_DB20_fullstate,
    protocol_agent_DB20_onlystate,
    protocol_agent_DB20_timestamps,
    PROTOCOL_FULL,
    PROTOCOL_NORMAL,
    protocol_simulator_DB20_timestamps,
    ProtocolDesc,
    RobotName,
    RobotObservations,
    RobotPerformance,
    RobotState,
    Scenario,
    SetMap,
    SetRobotCommands,
    SimulationState,
    SpawnDuckie,
    SpawnRobot,
    Step,
)
from duckietown_world import Tile
from duckietown_world.rules import EvaluatedMetric, RuleEvaluationResult

from zuper_nodes import ExternalProtocolViolation, RemoteNodeAborted
from zuper_nodes_wrapper import Profiler, ProfilerImp, logger
from zuper_nodes_wrapper.struct import MsgReceived
from zuper_nodes_wrapper.wrapper_outside import ComponentInterface

config = {
    "timeout_regular": 120,
    "timeout_initialization": 120,
    "fifo_dir": "/fifos",
    "sim_in": "/fifos/simulator-in",
    "sim_out": "/fifos/simulator-out",
    "seed": 888,
    "physics_dt": 0.05
}

def robot_stats(fn, dn_i, pc_name):
    Tile.style = "synthetic"
    evaluated = read_and_draw(fn, dn_i, pc_name)

    stats = {}
    for k, evr in evaluated.items():
        assert isinstance(evr, RuleEvaluationResult)
        for m, em in evr.metrics.items():
            assert isinstance(em, EvaluatedMetric)
            assert isinstance(m, tuple)
            if m:
                M = "/".join(m)
            else:
                M = k
            stats[M] = float(em.total)
    return stats

async def main_async(cie: dc.ChallengeInterfaceEvaluator, log_dir: str, scenarios: List[Scenario]):
    all_player_robots: Set[RobotName] = set()
    all_player_robots.add("ego0")
    all_controlled_robots: Dict[RobotName, str] = {}
    all_controlled_robots["ego0"] = "PROTOCOL_NORMAL"
    # episode = episodes[0]
    if not os.path.exists(config["fifo_dir"]):
        os.makedirs(config["fifo_dir"])
    fifo_in = os.path.join(config["fifo_dir"], "ego0-in")
    fifo_out = os.path.join(config["fifo_dir"], "ego0-out")

    if os.path.exists(fifo_in): os.remove(fifo_in)
    if os.path.exists(fifo_out): os.remove(fifo_out)
    if os.path.exists(config["sim_in"]): os.remove(config["sim_in"])
    if os.path.exists(config["sim_out"]): os.remove(config["sim_out"])

    # This is long running, previously managed by timeout
    agent_ci = ComponentInterface(
        fifo_in,
        fifo_out,
        expect_protocol=protocol_agent_DB20_timestamps,
        nickname="ego0",
        timeout=config["timeout_regular"],
    )
    agent_ci._get_node_protocol(timeout=config["timeout_initialization"])

    logger.debug("Now initializing sim connection", sim_in=config["sim_in"], sim_out=config["sim_out"])
    # This is long running, previously managed by timeout
    sim_ci = ComponentInterface(
        config["sim_in"],
        config["sim_out"],
        expect_protocol=protocol_simulator_DB20_timestamps,
        nickname="simulator",
        timeout=config["timeout_regular"],
    )
    try:
        sim_ci._get_node_protocol(timeout=config["timeout_initialization"])

        per_episode = {}

        sim_ci.write_topic_and_expect_zero("seed", config["seed"])
        agent_ci.write_topic_and_expect_zero("seed", config["seed"])
        for scenario in scenarios:
            dn = os.path.join(log_dir, scenario.scenario_name)
            if os.path.exists(dn):
                shutil.rmtree(dn)

            if not os.path.exists(dn):
                os.makedirs(dn)
            fn = os.path.join(dn, "log.gs2.cbor")

            fn_tmp = fn + ".tmp"
            fw = open(fn_tmp, "wb")

            agent_ci.cc(fw)
            sim_ci.cc(fw)

            logger.info(f"Now running episode {scenario.scenario_name}")

            try:
                length_s = await run_episode(
                    sim_ci,
                    agent_ci,
                    scenario=scenario,
                    physics_dt=config["physics_dt"],
                )
                logger.info(f"Finished episode {scenario.scenario_name} with length {length_s:.2f}")
            except:
                msg = "Anomalous error from run_episode()"
                logger.error(msg, e=traceback.format_exc())
                raise
            finally:
                fw.close()
                os.rename(fn_tmp, fn)

            logger.debug("Now creating visualization and analyzing statistics.")

            if length_s == 0:
                continue

            with ProcessPoolExecutor(max_workers=10) as executor:
                output_video = os.path.join(dn, "ui_image.mp4")
                # output_gif = os.path.join(dn, "ui_image.gif")
                # executor.submit(ui_image_bg, fn=fn, output_video=output_video, output_gif=output_gif)
                make_video_ui_image(log_filename=fn, output_video=output_video)
                # out_video = os.path.join(dn, "camera.mp4")
                # out_gif = os.path.join(dn, "camera.gif")
                # executor.submit(ui_video2, fn, out_video, "ego0", banner_bottom_fn, out_gif)

                results_stats = executor.submit(robot_stats, fn, dn, "ego0")
                per_episode[scenario.scenario_name] = results_stats.result()
    finally:
        agent_ci.close()
        sim_ci.close()

    cie.set_score("per-episodes", per_episode)

def main(scoring_root, scenario_path, fifos_dir):
    config.update({
        "fifo_dir": fifos_dir,
        "sim_in": fifos_dir + "/simulator-in",
        "sim_out": fifos_dir + "/simulator-out",
    })

    if not os.path.exists(scoring_root):
        os.makedirs(scoring_root)
    
    with open(scoring_root + "/dummyfile", "w"):
        # File required for integrity check on next call
        pass

    with dc.scoring_context(scoring_root) as cie:
        try:
            logdir = os.path.join(cie.root, "logdir")
            if not os.path.exists(logdir):
                os.makedirs(logdir)

            files = [entry for entry in os.scandir(scenario_path) if entry.is_file() and entry.name.endswith(".yaml")]
            files.sort(key=lambda x: x.name)
            scenarios = []
            for entry in files:
                name = entry.name[:-5]
                print(f"Adding map {name} to list of scenarios")
                tilesize = 0.585
                x = 0
                y = 0
                with open(entry.path[:-5] + ".start.txt") as startfile:
                    xy = startfile.readline().split()
                    x = int(xy[0])
                    y = int(xy[1])
                
                x *= tilesize
                y *= tilesize
                x += tilesize * 0.2
                y += tilesize * 0.3

                with open(entry.path, "r") as file:
                    scenario = Scenario(
                        name, file.read(), ["ego0"], {
                            "ego0": ScenarioRobotSpec(
                                RobotConfiguration(
                                    # Duckie posisition is in meters 0,0 is bottom left 0.0 theta is facing right
                                    FriendlyPose(x, y, 0.0),
                                    FriendlyVelocity(0.0,0.0,0.0)),
                                "red", "", True, PROTOCOL_NORMAL)
                        },
                        {}, "")
                    scenarios.append(scenario)
            asyncio.run(main_async(cie, logdir, scenarios), debug=True)
            cie.set_score("simulation-passed", 1)
        except:
            cie.error(f"weird exception: {traceback.format_exc()}")
            raise
        finally:
            cie.info("saving files")
            cie.set_evaluation_dir("episodes", logdir)


#TODO
async def run_episode(
    sim_ci: ComponentInterface,
    agent_ci: ComponentInterface,
    physics_dt: float,
    scenario: Scenario,
) -> float:
    episode_length_s = 200 #config["episode_length_s"]

    # clear simulation
    sim_ci.write_topic_and_expect_zero("clear")
    # set map data
    sim_ci.write_topic_and_expect_zero("set_map", SetMap(map_data=scenario.environment))

    # spawn robot
    for robot_name, robot_conf in scenario.robots.items():
        sp = SpawnRobot(
            robot_name=robot_name,
            configuration=robot_conf.configuration,
            playable=robot_conf.controllable,
            owned_by_player=robot_name in scenario.player_robots,
            color=robot_conf.color,
            simulate_camera=True,
        )
        sim_ci.write_topic_and_expect_zero("spawn_robot", sp)
    for duckie_name, duckie_config in scenario.duckies.items():
        sp = SpawnDuckie(name=duckie_name, color=duckie_config.color, pose=duckie_config.pose)
        sim_ci.write_topic_and_expect_zero("spawn_duckie", sp)

    episode_start = EpisodeStart(scenario.scenario_name, yaml_payload=scenario.payload_yaml)
    # start episode
    sim_ci.write_topic_and_expect_zero("episode_start", episode_start)
    agent_ci.write_topic_and_expect_zero("episode_start", episode_start)

    current_sim_time: float = 0.0
    steps: int = 0
    # for now, fixed timesteps

    loop = asyncio.get_event_loop()

    stop_at = None
    with ThreadPoolExecutor(max_workers=10) as executor:
        while True:
            steps += 1
            if stop_at is not None:
                if steps == stop_at:
                    logger.info(f"Reached {steps} steps. Finishing. ")
                    break
            if current_sim_time >= episode_length_s:
                logger.info(f"Reached {episode_length_s:.1f} seconds. Finishing. ")
                break

            # tt = TimeTracker(steps)
            t_effective = current_sim_time

            f = functools.partial(
                sim_ci.write_topic_and_expect,
                "dump_state",
                DumpState(),
                expect="state_dump",
            )
            state_dump: MsgReceived[DTSimStateDump] = await loop.run_in_executor(executor, f)

            for robot_name in scenario.robots:
                grs = GetRobotState(robot_name=robot_name, t_effective=t_effective)
                f = functools.partial(
                    sim_ci.write_topic_and_expect,
                    "get_robot_state",
                    grs,
                    expect="robot_state",
                )
                _recv: MsgReceived[RobotState] = await loop.run_in_executor(executor, f)

            for duckie_name in scenario.duckies:
                rs = GetDuckieState(duckie_name, t_effective)
                f = functools.partial(
                    sim_ci.write_topic_and_expect,
                    "get_duckie_state",
                    rs,
                    expect="duckie_state",
                )
                await loop.run_in_executor(executor, f)

            f = functools.partial(
                sim_ci.write_topic_and_expect, "get_sim_state", expect="sim_state"
            )
            recv: MsgReceived[SimulationState] = await loop.run_in_executor(executor, f)

            sim_state: SimulationState = recv.data
            if steps % 20 == 0: logger.info("Sim state: ", sim_state=sim_state)

            if sim_state.done:
                if stop_at is None:
                    NMORE = 15
                    stop_at = steps + NMORE
                    msg = (
                        f"Breaking because of simulator. Will break in {NMORE} more steps at step "
                        f"= {stop_at}."
                    )
                    logger.info(msg, sim_state=sim_state)
                else:
                    msg = f"Simulation is done. Waiting for step {stop_at} to stop."
                    logger.info(msg)

            f = functools.partial(
                sim_ci.write_topic_and_expect,
                "get_robot_performance",
                "ego0",
                expect="robot_performance"
            )

            _recv: MsgReceived[RobotPerformance] = await loop.run_in_executor(executor, f)

            get_robot_observations = GetRobotObservations("ego0", t_effective)

            f = functools.partial(
                sim_ci.write_topic_and_expect,
                "get_robot_observations",
                get_robot_observations,
                expect="robot_observations",
            )
            recv_observations: MsgReceived[RobotObservations]
            recv_observations = await loop.run_in_executor(executor, f)
            ro: RobotObservations = recv_observations.data
            obs = cast(DB20ObservationsWithTimestamp, ro.observations)
            map_data = cast(str, scenario.environment)

            # if pr == PROTOCOL_FULL:
            #     obs_plus = DB20ObservationsPlusState(
            #         camera=obs.camera,
            #         odometry=obs.odometry,
            #         your_name=agent_name,
            #         state=state_dump.data.state,
            #         map_data=map_data,
            #     )
            # elif pr == PROTOCOL_NORMAL:
            obs_plus = DB20ObservationsWithTimestamp(
                camera=obs.camera, odometry=obs.odometry
            )
            # elif pr == PROTOCOL_STATE:
            #     obs_plus = DB20ObservationsOnlyState(
            #         your_name=agent_name,
            #         state=state_dump.data.state,
            #         map_data=map_data,
            #     )
            # else:
            #     raise NotImplementedError(pr)
            f = functools.partial(
                agent_ci.write_topic_and_expect_zero,
                "observations",
                obs_plus,
            )
            await loop.run_in_executor(executor, f)

            get_commands = GetCommands(t_effective)
            # noinspection PyProtectedMember
            f = functools.partial(agent_ci._write_topic, "get_commands", get_commands)
            await loop.run_in_executor(executor, f)

            f = functools.partial(agent_ci.read_one, "commands")
            msg = await loop.run_in_executor(executor, f)
            cmds = msg.data
            set_robot_commands = SetRobotCommands("ego0", t_effective, cmds)
            f = functools.partial(
                sim_ci.write_topic_and_expect_zero,
                "set_robot_commands",
                set_robot_commands,
            )
            await loop.run_in_executor(executor, f)

            current_sim_time += physics_dt
            f = functools.partial(
                sim_ci.write_topic_and_expect_zero, "step", Step(current_sim_time)
            )
            await loop.run_in_executor(executor, f)

            # Needed to generate ui images in the log, which will be extracted when analyzed
            f = functools.partial(
                sim_ci.write_topic_and_expect,
                "get_ui_image",
                None,
                expect="ui_image",
            )
            _r_ui_image: MsgReceived[JPGImage] = await loop.run_in_executor(executor, f)

            if steps % 100 == 0:
                # gc.collect()
                pass
            if steps % 20 == 0:
                logger.info(f"Sim time: {steps} steps = {steps/20} secs")

    return current_sim_time

if __name__ == "__main__":
    main("../scoring_root", "../maps", "../fifos")
