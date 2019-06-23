import sys
from sdl2 import *
from threading import Thread
import time
import subprocess
import os

from board import *

def parseLine(line):
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
				pv.append(stdToCoord(tok))
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
		heatInfos = np.array([float(tok) for tok in txt])
		return infos, heatInfos
	return None

# Thanks stackoverflow ! 
# https://stackoverflow.com/questions/375427/non-blocking-read-on-a-subprocess-pipe-in-python
def enqueue_output(out, katago):
	for line in iter(out.readline, b''):
		katago.lastAnalyse = parseLine(line.decode())
		if katago.lastAnalyse: # do not care if this is not relevant info
			ev = SDL_Event()
			ev.type = katago.eventID
			SDL_PushEvent(ev)
	out.close()

class KataGo:

	"""'<class KataGo>' is a binder to the real KataGo program.
	Creating a KataGo object will spawn a child thread one can send 
	commands to and get information.

	Below are values to be modified according to KataGo's directory
	on your computer."""

	BIN = "../KataGo/cpp/main"
	STDMODEL = "../KataGo/cpp/models/g103-b6c96-s103408384-d26419149.txt.gz"
	CONFIG = "gtp_analysis.cfg"
	THINKING_TIME = 1000 # in centiseconds
	ANALYSIS_CMD = "kata-analyze interval {} ownership true"
	ANALYSIS_DIR = "analysis"

	def __init__(self, eventID, config=None, model=None):
		
		if not config: config = KataGo.CONFIG
		if not model: model = KataGo.STDMODEL

		cmd = "{} gtp -model {} -config {}".format(
			KataGo.BIN, KataGo.STDMODEL, KataGo.CONFIG)
		self.pid = subprocess.Popen(cmd.split(), stdin=subprocess.PIPE, 
			stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1)
		if not self.pid: # TODO: check the doc of subprocess.Popen
			raise Exception("Error when starting KataGo")

		self.lastAnalyse = None
		self.eventID = eventID

		self.stdin = self.pid.stdin.fileno()
		self.stdout = self.pid.stdout.fileno()

		self.thread = Thread(target=enqueue_output, args=(self.pid.stdout, self))
		self.thread.daemon = True
		self.thread.start()

	def sendCommand(self, cmd):
		"""Send a raw command to katago"""
		cmd += "\n"
		os.write(self.stdin, cmd.encode())

	def setBoardsize(self, size):
		"""Set the boardsize of KataGo"""
		self.sendCommand("boardsize {}".format(size))

	def setKomi(self, komi):
		"""Set the komi of KataGo"""
		self.sendCommand("komi {}".format(komi))

	def playStone(self, pla, txt):
		"""play a stone on intersection corresponding to 'txt'"""
		player = {Board.BLACK: "B", Board.WHITE: "W"}
		cmd = "play {} {}".format(player[pla], txt)
		self.sendCommand(cmd)

	def playCoord(self, i, j, pla, size=19):
		"""Play a stone at coordinates (i, j)"""
		txt = coordToStd(i, j, size)
		self.playStone(pla, txt)

	def undo(self):
		"""Undo the previous move"""
		self.sendCommand("undo")

	def clearBoard(self):
		"""Clear the board of KataGo"""
		self.sendCommand("clear_board")

	def clearCache(self):
		"""Clear KataGo's cache"""
		self.sendCommand("clear-cache")

	def stop(self):
		"""Stop what KataGo is doing.

		Use it when you want to stop an analysis currently running."""
		self.sendCommand("stop")

	def close(self):
		"""Close KataGo"""
		self.sendCommand("quit")

	def playSeq(self, moves, clear=False):
		"""Play a sequence of moves"""
		if clear: self.clear()
		for pla, i, j in moves:
			self.playCoord(i, j, pla)


	# More serious commands

	def analyse(self, ttime=None):
		"""Start KataGo's analysis - time is in centiseconds and controls
		at which frequency katago's send analysis informations."""
		if not ttime: ttime = KataGo.THINKING_TIME
		cmd = KataGo.ANALYSIS_CMD.format(ttime)
		self.sendCommand(cmd)

	def waitOutput(self, csleep=10):
		"""Wait for KataGo to output something. If there is no input at
		the current moment, sleep for csleep centi-seconds. """
		line = self.queue.get()
		return line.decode()

	def pollOutput(self):
		"""Poll the last output from katago"""
		try: 
			line = self.queue.get_nowait() # or .get(timeout=...)
		except Empty:
			return None
		else:
			return line.decode()

	def waitAnalysis(self, stop=True):
		"""Wait for an output of the analysis.
		Warning - will deadlock if user did not start any analysis.

		Return (heat informations, informations) in a tuple."""
		while True:
			line = self.waitOutput()
			tmp = parseLine(line)
			if not tmp: continue
			break
		return tmp

	def getAnalysis(self, stop=False):
		"""Get the last analysis from katago. If there are no such analysis,
		return empty analysis data [], "" """
		infos, heatInfos = [], ""
		while True:
			# Get last line - if there are no line, stop and return current 
			# infos and heatInfos
			line = self.pollOutput()
			if not line: 
				return infos, heatInfos

			# Parse last line - if it does not work, continue 
			tmp = parseLine(line)
			if not tmp: continue
			infos, heatInfos = tmp
			

	