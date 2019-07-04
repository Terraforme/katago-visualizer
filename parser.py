import argparse

parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter,
	description="KataGo Analyzer - no description :-)\n")

parser.add_argument("--from-sgf", type=str, dest="sgffile",
	help="load a sgf file")
parser.add_argument("--katago-off", dest="skatago", action="store_false",
	help="launch with no KataGo thread")
parser.add_argument("--silent", dest="silent", action="store_true",
	help="hide all default analysis")
parser.add_argument("--auto-play", type=str, dest="play",
	help="set to white or black to make katago play automatically")
parser.add_argument("--thinking-time", type=float, dest="kttime",
	help="set the thinking time of katago in auto play mode")
parser.set_defaults(skatago=True)
parser.set_defaults(silent=False)
parser.set_defaults(kttime=10.0)

def parse_args():
	return parser.parse_args()
