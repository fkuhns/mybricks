#!/usr/bin/env python3
# Run smartCar/main.py on the laptop against simulated hardware.
#
#   python3 sim/run.py sim/scenarios/i2c_faults.py
#   python3 sim/run.py sim/scenarios/dist_room.py -q       # hide app prints
#   python3 sim/run.py sim/scenarios/ir_drive.py -v        # more sim detail
#   python3 sim/run.py --all                               # every scenario, pass/fail
#
# A scenario is a python file with:
#   MODE        = "MODE_1"    # name of a MODE_* constant in main.py, or an int
#   DURATION_MS = 20_000
#   def scenario(sim): ...    # schedule inputs, faults and checks (see README)
import argparse
import builtins
import importlib.util
import os
import subprocess
import sys
import time as _host_time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def install(start_ms):
    # stub modules first on the path, then the real code
    sys.path[:0] = [HERE, os.path.join(ROOT, "common"), os.path.join(ROOT, "smartCar")]
    import simcore
    import utime
    import micropython

    simcore.SIM.now_us = simcore.SIM.t0_us = start_ms * 1000
    builtins.const = micropython.const   # MicroPython lets const() be used unimported
    builtins.print = simcore.SIM.app_print
    # "time" is built into CPython, so add the MicroPython calls to it
    for name in ("ticks_ms", "ticks_us", "ticks_diff", "ticks_add", "sleep_ms", "sleep_us"):
        setattr(_host_time, name, getattr(utime, name))
    return simcore


def load_scenario(path):
    spec = importlib.util.spec_from_file_location("scenario", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_one(path, args):
    simcore = install(args.start_ms)
    sim = simcore.SIM
    sim.verbose = args.verbose
    sim.app_log = not args.quiet

    try:
        scen = load_scenario(path)
        import main

        mode = scen.MODE if isinstance(scen.MODE, int) else getattr(main, scen.MODE)
        sim.end(args.until or getattr(scen, "DURATION_MS", 20_000))
        scen.scenario(sim)
    except BaseException:
        builtins.print = simcore._print
        raise
    sim.log("START", "%s  mode 0x%02x" % (os.path.basename(path), mode))

    try:
        sim.app = main.MyApp(mode)
        sim.app.run()
    except simcore.SimStop:
        sim.log("END", "time limit reached")
    except simcore.SimReset:
        pass
    except Exception as e:
        sim.log("CRASH", "app raised %r" % e)
        sim.results.append((False, sim.now_ms(), "app crashed: %r" % e))
    finally:
        builtins.print = simcore._print

    return 0 if sim.summary() else 1


def run_all(args):
    scen_dir = os.path.join(HERE, "scenarios")
    failed = []
    for name in sorted(os.listdir(scen_dir)):
        if not name.endswith(".py"):
            continue
        r = subprocess.run([sys.executable, __file__, os.path.join(scen_dir, name), "-q"],
                           capture_output=True, text=True)
        status = "PASS" if r.returncode == 0 else "FAIL"
        print("%-24s %s" % (name, status))
        if r.returncode:
            failed.append(name)
            tail = [l for l in r.stdout.splitlines() if "FAIL" in l or "CRASH" in l]
            for l in tail[-10:]:
                print("    " + l.strip())
            if r.stderr:
                print("    " + r.stderr.strip().splitlines()[-1])
    return 1 if failed else 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("scenario", nargs="?")
    p.add_argument("--all", action="store_true", help="run every scenario in sim/scenarios")
    p.add_argument("-q", "--quiet", action="store_true", help="hide the app's own prints")
    p.add_argument("-v", "--verbose", action="count", default=1, help="more simulator detail")
    p.add_argument("--until", type=int, help="override DURATION_MS")
    p.add_argument("--start-ms", type=int, default=0,
                   help="clock start, e.g. 1073731000 to test ticks wraparound")
    args = p.parse_args()
    if args.all:
        sys.exit(run_all(args))
    if not args.scenario:
        p.error("give a scenario file or --all")
    sys.exit(run_one(args.scenario, args))


if __name__ == "__main__":
    main()
