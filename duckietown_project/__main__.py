def run_map(args):
    import map_gen
    map_gen.init_args(args)
    the_map = map_gen.gen_map()
    map_gen.save_map(args.file_name, the_map)


def run_auto_control(args):
    import auto_control
    auto_control.init_args(args)
    auto_control.run()


def run_automated(args):
    import run_automated
    run_automated.main()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    from map_gen import init_args_parser as init_map_gen
    map_parser = subparsers.add_parser("map")
    init_map_gen(map_parser)
    map_parser.set_defaults(func=run_map)

    from auto_control import init_args_parser as init_auto_control
    auto_parser = subparsers.add_parser("auto")
    init_auto_control(auto_parser)
    auto_parser.set_defaults(func=run_auto_control)

    automated_parser = subparsers.add_parser("automated")
    automated_parser.set_defaults(func=run_automated)

    args = parser.parse_args()
    args.func(args)