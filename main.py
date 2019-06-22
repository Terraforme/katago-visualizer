#!/usr/bin/python3

import sgffiles
from board import *

if __name__ == "__main__":
	path = input("load: ")
	gdata, setup, moves, rules = sgffiles.load_sgf_moves(path)
	board = Board(size=gdata.size)
	board.setSequence(setup)
	board.render_seq(moves)