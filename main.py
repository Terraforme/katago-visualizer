#!/usr/bin/python3

from render import run
from parser import *

from katago import KataGo
import yaml

with open("config.yaml", 'r') as stream:
    lconfig = yaml.safe_load(stream)

# Set KataGo's configuration
KataGo.BIN = lconfig["KataGo.BIN"]
KataGo.STDMODEL = lconfig["KataGo.STDMODEL"]
KataGo.CONFIG = lconfig["KataGo.CONFIG"]

if __name__ == "__main__":

	print("Loaded configuration:", lconfig)

	run()
	raise SystemExit(0)
