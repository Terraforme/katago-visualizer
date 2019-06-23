#!/usr/bin/python3

import sgffiles
from board import *
from render import run
from katago import KataGo
import sys


if __name__ == "__main__":
	path = sys.argv[1] if len(sys.argv) > 1 else input("load: ")
	gdata, setup, moves, rules = sgffiles.load_sgf_moves(path)
	board = Board(size=gdata.size)
	board.setSequence(setup)
	board.render_seq(moves)

	kata = KataGo()
	kata.setBoardsize(gdata.size)
	kata.setKomi(gdata.komi)
	kata.playSeq(setup)
	kata.playSeq(moves)
	
	run(board, kata)
	raise SystemExit(0)
