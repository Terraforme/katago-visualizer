import argparse

parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter,
	description="KataGo Analyzer - no description :-)\n")

parser.add_argument("--from-sgf", type=str, dest="sgffile",
	help="load a sgf file")
parser.add_argument("--katago-off", dest="skatago", action="store_false",
	help="launch with no KataGo thread")
parser.add_argument("--silent", dest="silent", action="store_true",
	help="hide all default analysis")
parser.set_defaults(skatago=True)
parser.set_defaults(silent=False)

def parse_args():
	return parser.parse_args()
