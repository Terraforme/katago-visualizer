#!/usr/bin/python3

import argparse
from render import run

parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter,
	description="KataGo Analyzer - no description :-)\n")

parser.add_argument("--from-sgf", type=str, dest="sgffile",
	help="load a sgf file")
parser.add_argument("--katago-off", dest="skatago", action="store_false",
	help="launch with no KataGo thread")
parser.set_defaults(skatago=True)


if __name__ == "__main__":


	args = parser.parse_args()
	skatago = args.skatago
	sgf = args.sgffile

	run(sgf, skatago)

	raise SystemExit(0)
