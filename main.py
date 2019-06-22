#!/usr/bin/python3

import sgffiles
from board import *
from render import run
from katago import KataGo


if __name__ == "__main__":
	path = input("load: ")
	gdata, setup, moves, rules = sgffiles.load_sgf_moves(path)
	board = Board(size=gdata.size)
	board.setSequence(setup)
	board.render_seq(moves)
	
	kata = KataGo()
	kata.setBoardsize(gdata.size)
	kata.setKomi(gdata.komi)
	kata.playSeq(setup)
	kata.playSeq(moves[:20])
	kata.analyse()
	print(kata.waitAnalysis())
	kata.close()
	print("Everything went well !")
	# run()