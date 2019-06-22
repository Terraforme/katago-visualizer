#!/usr/bin/python3

import numpy as np
from matplotlib import pyplot as plt
from math import sin, cos, pi

import subprocess
import os
import time

# Importing libraries from katago
# You have to change 
import sys
sys.path.append("../KataGo/python/")
import data
import board

N = 19
INFINITY = 1e6

KATAGO_BIN = "../KataGo/cpp/main"
KATAGO_MODEL = "../KataGo/cpp/models/g103-b6c96-s103408384-d26419149.txt.gz"
KATAGO_CONFIG = "../KataGo/cpp/configs/gtp_example.cfg"
KATAGO = "{} gtp -model {} -config {}".format(
	KATAGO_BIN, KATAGO_MODEL, KATAGO_CONFIG).split()
print(KATAGO)
# cmd is './main gtp -model models/g103-b6c96-s103408384-d26419149.txt.gz -config configs/gtp_example.cfg'

THINKING_TIME = "1000" # centiseconds
ANALYSE_CMD = "kata-analyze interval {} ownership true\n".format(THINKING_TIME)
ANALYSIS_DIR = "analysis/"

try:
	os.mkdir(ANALYSIS_DIR)
	print("Directory", ANALYSIS, "created.")
except:
	pass

SGFEXAMPLE = "../../ti143.sgf"

def dist(mov1, mov2):
	""" Return the euclidian distance between two moves"""
	i, j = mov1
	u, v = mov2
	return ((i - u)**2 + (j - v)**2)**.5

def setAnalyseTime(sec):
	"""Set KataGo's thinking time (in seconds)"""
	global THINKING_TIME
	THINKING_TIME = str(int(sec*100))
	global ANALYSE_CMD 
	ANALYSE_CMD = "kata-analyze interval {} ownership true\n".format(THINKING_TIME)

def validCoordinates(i, j, size=N):
	"""Return whether (i, j) are valid coordinates or not"""
	if i >= N or j >= N: return False
	if i < 0 or j < 0: return False
	return True

def toCoordinates(num, size=N):
	# print("move {}: ".format(num), num // size, ",",num % size)
	return (num // (size+1) - 1, num % (size+1))

def moveToString(pla, loc, size=N):
	p = {1: "B", 2:"W"}
	c = "ABCDEFGHJKLMNOPQRST"
	(i, j) = toCoordinates(loc)
	txt = "play {} {}{}".format(p[pla], c[i], j)
	return txt

def stringToMove(txt):
	c = "ABCDEFGHJKLMNOPQRST"
	j = c.index(txt[0])
	i = int(txt[1:])-1
	return i, j


def drawTriangle(ax, x, y, radius=0.3, zlayer=11):
	a = np.array([0, 1])
	b = np.array([-cos(pi/6), -sin(pi/6)])
	c = np.array([ cos(pi/6), -sin(pi/6)])
	X = x + radius * np.array([a[0], b[0], c[0], a[0]])
	Y = y + radius * np.array([a[1], b[1], c[1], a[1]])
	ax.plot(X, Y, color="red", zorder=zlayer)

class Board:
	
	def __init__(self, size=N):
		self.stones = np.zeros(shape=(size,size))
		self.heat = np.zeros(shape=(size,size))
		self.size = size
		self.lastmov = 0, 0
		self.parity = 0 # 1 : white to play, 0 : black to play
		self.infos = []
	
	def updLastMove(self, loc):
		self.lastmov = loc % (self.size+1) - 1, loc // (self.size+1) - 1
	
	def rot90(self, num=-1):
		self.stones = np.rot90(self.stones, num)
		self.heat = np.rot90(self.heat, -num)
	
	def getHeat(self, i, j):
		"""Return the heat at some coordinates"""
		return self.heat[j][i]
	
	def setHeat(self, i, j, heat):
		"""Hardcode the heat at specific coordinates"""
		self.heat[j][i] = heat
	
	def getChainHeat(self, chain):
		"""Return the average heat over a chain"""
		if chain == []: return 0
		heat = 0
		for (i, j) in chain:
			heat += self.getHeat(i, j)
		return heat / len(chain)
	
	def getChain(self, i, j):
		"""Return the list of all stones linked to (i, j) having the
		same color"""
		N = self.size
		seen = np.zeros(shape=(N,N)) # matrix of False
		color = self.stones[i][j]
		chain = []
		if color == 0: return []
		
		def getChain_aux(i, j):
			seen[i][j] = True
			if color != self.stones[i][j]: return None
			
			chain.append((i,j))
			if validCoordinates(i-1,j,N) and not seen[i-1][j]:
				getChain_aux(i-1, j)
			if validCoordinates(i+1,j,N) and not seen[i+1][j]:
				getChain_aux(i+1, j)
			if validCoordinates(i,j-1,N) and not seen[i][j-1]:
				getChain_aux(i, j-1)
			if validCoordinates(i,j+1,N) and not seen[i][j+1]:
				getChain_aux(i, j+1)
				 
		getChain_aux(i, j)
		return chain
	
	def getGroups(self):
		"""Return the list of all groups"""
		N = self.size
		seen = np.zeros(shape=(N,N)) # matrix of False
		groups = []
		for i in range(N):
			for j in range(N):
				if seen[i][j]: continue
				chain = self.getChain(i, j)
				if chain == []: continue
				groups.append(chain)
				for (u, v) in chain:
					seen[u][v] = True

		return groups
	
	def mergeGroupsHeat(self):
		"""Merge the heat on each group by doing the average"""
		groups = self.getGroups()
		for chain in groups:
			heat = self.getChainHeat(chain)
			for i, j in chain:
				self.setHeat(i, j, heat)

	def clear(self):
		size = self.size
		self.stones = np.zeros(shape=(size,size))
		self.heat = np.zeros(shape=(size,size))
		self.infos = []
	
	def fromText(self, txt):
		accepted = [".", "X", "O", "*"]
		conv = {".":0, "X": 1, "O": 2, "*":0}
		size = self.size
		txt = txt.split()
		tokens = []
		for tok in txt: 
			if tok in accepted: 
				tokens.append(tok)
		self.clear()
		for i in range(size):
			for j in range(size):
				self.stones[i][j] = conv[tokens[(size-1-i)*size+j]]
	
	def fromSGF(self, path, movnum=99, stdin=True):
		if (stdin): movnum = int(input("move number:"))
		self.clear()
		(metadata, setup, sgfmoves, rules) = data.load_sgf_moves_exn(path)
		b = board.Board(size=self.size)
		seq = []
		for (pla, loc) in setup:
			b.play(pla, loc)
			seq.append(moveToString(pla, loc, self.size))
		for i in range(movnum):
			if (i >= len(sgfmoves)): break
			(pla, loc) = sgfmoves[i]
			b.play(pla, loc)
			seq.append(moveToString(pla, loc, self.size))
			self.updLastMove(loc)
			self.parity = 0 if pla == 1 else 1
		self.fromText(b.to_string())
		return seq

	def parseLine(self, line):
		"""Load informations from an extracted line. Return True if the line
		was valid, and False otherwise."""
		#print(line)
		txt = line.split()
		i = 0
		infos = []
		visits = 0
		winrate = 0
		scoreMean = 0
		scoreStDev = 0
		pv = []
		correct = False
		while i < len(txt):
			tok = txt[i]
			if tok == "visits": 
				i, tok = i+1, txt[i+1]
				visits = int(tok)
			elif tok == "winrate": 
				i, tok = i+1, txt[i+1]
				winrate = float(tok)
			elif tok == "scoreMean":
				i, tok = i+1, txt[i+1]
				scoreMean = float(tok)
			elif tok == "scoreStDev":
				i, tok = i+1, txt[i+1]
				scoreStDev = float(tok)
			elif tok == "pv":
				pv = []
				i, tok = i+1, txt[i+1]
				while tok != "info" and tok != "ownership":
					pv.append(stringToMove(tok))
					i, tok = i+1, txt[i+1]
				infos.append((visits, winrate, scoreMean, scoreStDev, pv))			 
			
			if tok == "ownership":
				correct = True
				break
			i += 1
		if correct:
			if txt[i] == "ownership":
				txt = txt[i+1:]
			else :
				txt = txt[i:]
			self.loadHeat(' '.join(tok for tok in txt))
			self.infos = infos
			return True
		return False
			
		
	def loadHeatFromLine(self, line):
		"""Load heat informations from an extracted line. Return True if 
		the line had heat information, and False otherwise."""
		txt = line.split()
		readmode = False
		val = []
		for (i, tok) in enumerate(txt):
			if tok == "ownership": 
				readmode = True
				txt = txt[i+1:]
				break
		if readmode:
			# print("else stmt")
			txt = ' '.join(tok for tok in txt)
			self.loadHeat(txt)
			return True
		return False
	
	def loadHeat(self, txt, mergeOnChains=True):
		N = self.size
		txt = txt.split()
		val = [float(token) for token in txt]
		self.heat = np.zeros(shape=(N,N))
		for i in range(N):
			for j in range(N):
				self.heat[i][j] = val[N*(N-1-i)+(N-1-j)]
		if not self.parity: self.heat = -self.heat
		if mergeOnChains: self.mergeGroupsHeat()
	
	def drawGoban(self, ax):
		"""Draw an empty goban"""
		N = self.size
		for i in range(N):
			ax.plot([0, N-1], [i, i], color="black", clip_on=False)
			ax.plot([i, i], [0, N-1], color="black", clip_on=False)
		if N == 19:
			hoshi = [(3,  3), (3,  9), (3, 15), \
			         (9,  3), (9,  9), (9, 15), \
			         (15, 3), (15, 9), (15, 15)]
			for i, j in hoshi:
				dot = plt.Circle((i, j), 0.1, color="black")
				ax.add_artist(dot)
		

	def drawStone(self, ax, i, j, num=None, pla=None, fontsize=10):
		"""Draw the (i, j) stone on the board."""
		color = {1: "black", 2:"white"}
		colorext = {1: "white", 2: "black"}
		if not pla: c = self.stones[i][j]
		else: c = pla
		if c == "." or c == 0: return None
		stone = plt.Circle((i,j), 0.4, color=color[int(c)], clip_on=True, zorder = 5)
		stoneext = plt.Circle((i,j), 0.4, fill=False, color=colorext[int(c)], clip_on=True, zorder = 10)
		if num: # Writing a number
			ax.text(i, j, num, color=colorext[c], \
			horizontalalignment='center', verticalalignment='center', zorder=10, \
			fontsize=fontsize)
		ax.add_artist(stone)
		ax.add_artist(stoneext)
	
	def drawLastMove(self, ax):
		"""Draw a mark on the last move (blue circle)"""
		i, j = self.lastmov
		mark = plt.Circle((i,j), 0.2, fill=False, color="blue", clip_on=True, zorder = 25)
		ax.add_artist(mark)
		
	
	def drawVariation(self, ax, pv):
		"""Draw the variation pv"""
		switch = {1:2, 2:1}
		c = switch[1 if self.parity == 0 else 2]
		n = 1
		prevmov = 0, 0
		for i,j in pv:
			if n >= 10 and dist((i, j), prevmov) > 10: break
			fontsize = 10 if n < 10 else 7
			self.drawStone(ax, i, j, num=n, pla=c, fontsize=fontsize)
			c = switch[c]
			prevmov = i, j
			n += 1
	
	def drawMarks(self, ax):
		"""Draw a triangle on each probably dead stone. Merge stones into 
		groups to not draw aberrant things"""
		groups = self.getGroups()
		for chain in groups:
			i, j = chain[0]
			c = self.stones[i][j] 
			if c == 2: c = -1
			heat = self.getChainHeat(chain)
			if heat * c < 0:
				for i, j in chain:
					# print("@{}-{} dead stone: {} %".format(i, j, 100*self.heat[i][j]))
					drawTriangle(ax, i, j)
	
	def draw(self, ax, drawPV=True):
		color = {1: "black", 2:"white"}
		colorext = {1: "white", 2: "black"}
		N = self.size
		self.drawGoban(ax)
		for i in range(N):
			for j in range(N):
				self.drawStone(ax, i, j)

		if self.infos != [] and drawPV:
			c = 2 if self.parity == 0 else 1
			pla = {1:'B', 2:'W'}
			(visit, win, score, scoredev, pv) = self.infos[0]
			print(self.infos[0])
			self.drawVariation(ax, pv)
			ax.set_title("PV({}): win {:.2f}% score ({}){:.2f}".format(visit, 100*win, pla[c], score))

		self.drawMarks(ax)
		self.drawLastMove(ax)			   
		 
	def __str__(self):
		conv = {0: " .", 1: " X", 2: " O"} 
		txt = "   A B C D E F G H J K L M N O P Q R S T\n"
		rows = ["19", "18", "17", "16", "15", "14", "13", "12", "11", "10", \
				" 9", " 8", " 7", " 6", " 5", " 4", " 3", " 2", " 1"]
		size = self.size
		for i in range(size):
			txt += rows[i]
			for j in range(size):
				txt += self.stones[i][j]
			txt += "\n"
		return txt

def analyse(sgfpath, start=None, end=None, colormap='RdGy', writeOutput=True):
	"""Analyse a game."""
	anab = Board() # analysis board
	(metadata, setup, sgfmoves, rules) = data.load_sgf_moves_exn(sgfpath)
	b = board.Board(size=anab.size)
	katago = subprocess.Popen(KATAGO, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	if setup != []:
		os.write(katago.stdin.fileno(), "boardsize 19\nkomi 0.5\n".encode())
	else:
		os.write(katago.stdin.fileno(), "boardsize 19\nkomi 7.5\n".encode())

	# Set bounds
	movnum = len(sgfmoves)
	if not end: end = movnum
	if not start: start=1
	
	seq = []
	
	# Setup handicap stones
	for (pla, loc) in setup:
		b.play(pla, loc)
		seq.append(moveToString(pla, loc, anab.size)+"\n")
		os.write(katago.stdin.fileno(), seq[-1].encode())
	
	# Analyse the game
	for i in range(movnum):
		if (i >= len(sgfmoves)): break
		
		# Playing the move
		(pla, loc) = sgfmoves[i]
		b.play(pla, loc)
		seq.append(moveToString(pla, loc, anab.size)+"\n")
		anab.updLastMove(loc)
		os.write(katago.stdin.fileno(), seq[-1].encode())
		anab.parity = 0 if pla == 1 else 1 # 0 : white to play, 1 : black to
		anab.fromText(b.to_string())
		
		if i < start-1: continue
		if i >= end: break
		
		# Getting katago analysis
		# os.write(katago.stdin.fileno(), "showboard\n".encode())
		os.write(katago.stdin.fileno(), ANALYSE_CMD.encode())
		while True:
			line = katago.stdout.readline().decode()
			if anab.parseLine(line): break
		os.write(katago.stdin.fileno(), "stop\n".encode())
		
		# Board correcting rotation
		anab.rot90()
		
		# Getting picture
		fig, ax = plt.subplots()
		cax = ax.matshow(anab.heat, cmap=colormap)
		fig.colorbar(cax)
		anab.draw(ax)
		output_name = "analysis-mov {}.png".format(i+1) 
		if end == start or not writeOutput:
			fig.show()
		if writeOutput:
			fig.savefig(ANALYSIS_DIR + output_name)
			print("Output move {}: {}".format(i+1, output_name))
	
	print("Analysis is over")

def main(colormap='RdGy'): # 'binary'
	board = Board()
	seq = board.fromSGF(SGFEXAMPLE)
	seqtxt = "\n".join(mov for mov in seq) + "\n" + ANALYSE_CMD
	seqbin = seqtxt.encode()
	# print("Will send:", seqbin)
	katago = subprocess.Popen(KATAGO, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	os.write(katago.stdin.fileno(), seqbin)
	
	while True:
		line = katago.stdout.readline().decode()
		if board.loadHeatFromLine(line): break
	os.write(katago.stdin.fileno(), "stop\nquit\n".encode())
	
	# Doing a rotation
	board.rot90()
	
	fig, ax = plt.subplots()
	cax = ax.matshow(board.heat, cmap=colormap)
	fig.colorbar(cax)
	board.draw(ax)
	plt.show()
	fig.savefig('area.png')

if __name__ == "__main__":
	pass
