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
	t = time.time()
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
		elif tok == "scoreStdev":
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
			i += 1 # skip the 'ownership' token
			correct = True
			break
		i += 1
	if correct:
		heatInfos = np.zeros(361)
		for j in range(361):
			heatInfos[j] = float(txt[i+j])
		dt = time.time() - t
		return infos, heatInfos
	return None

# Thanks stackoverflow ! 
# https://stackoverflow.com/questions/375427/non-blocking-read-on-a-subprocess-pipe-in-python
def enqueue_output(out, katago):
	for line in iter(out.readline, b''):
		katago.updocount()
		# print("Balance:", katago.ocount - katago.icount)
		# katago.lastEventKey = katago.key
		katago.lastAnalyse = parseLine(line.decode())
		if katago.lastAnalyse and katago.uptodate(): 
			# do not care if this is not relevant info
			ev = SDL_Event()
			ev.type = katago.eventID
			SDL_PushEvent(ev)

		# Automatic analyze
		elif katago.isON() and not katago.isSearching() and katago.uptodate(): 
			# If katago.lastAnalyse is False, it means that KataGo is stopped
			# If moreover, KataGo is ON, we start the analysis.
			ttime = 100 # centiseconds
			katago.analyse(ttime)

	out.close()

class KataGo:

	"""'<class KataGo>' is a binder to the real KataGo program.
	Creating a KataGo object will spawn a child thread one can send 
	commands to and get information.

	Below are values to be modified according to KataGo's directory
	on your computer."""

	BIN = None
	STDMODEL = None
	CONFIG = None
	THINKING_TIME = 1000 # in centiseconds
	ANALYSIS_CMD = "kata-analyze interval {} ownership true"
	ANALYSIS_DIR = "analysis"

	def __init__(self, eventID, config=None, model=None, turnoff=False):
		"""
		- eventID - SDL event generated when KataGo makes a new analysis
		- config - optional, path to a configuration file
		- model - optional, path to a model (.txt.gz)
		- turnoff - optional. Is set to True, the KataGo is a dead end.
		  use it you want to use the app with no KataGo subprocess."""
		if turnoff:
			print("Warning: KataGo set OFF")
			self._ON = False
			return None
		else:
			self._ON = True

		if not config: config = KataGo.CONFIG
		if not model: model = KataGo.STDMODEL

		cmd = "{} gtp -model {} -config {}".format(
			KataGo.BIN, KataGo.STDMODEL, KataGo.CONFIG)
		self.pid = subprocess.Popen(cmd.split(), stdin=subprocess.PIPE, 
			stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1)
		if not self.pid: 
			raise Exception("Error when starting KataGo")

		self.lastAnalyse = None
		self.eventID = eventID
		
		# input count - number of sent commands
		self.icount = 0
		# output count - number of outputs (counting lines)
		# Waiting 3 lines at launch so initialized to -3
		self.ocount = -3 
		# Searching state (boolean)
		self.searching = False

		self.key = 0
		self.lastEventKey = 0 # FIXME: this is bad

		self.stdin = self.pid.stdin.fileno()
		self.stdout = self.pid.stdout.fileno()

		self.thread = Thread(target=enqueue_output, args=(self.pid.stdout, self))
		self.thread.daemon = True
		self.thread.start()

	def isON(self):
		"""
		Return True if KataGo is ON (automatic analysis)
		"""
		return self._ON

	def isSearching(self):
		"""
		Return if the KataGo thread is analyzing or not
		"""
		return self.searching

	def uptodate(self):
		"""
		Return True if KataGo is up to date with sent commands.
		"""
		return self.ocount == self.icount

	def updocount(self):
		"""
		Update output count.
		Cap it to the input count.
		"""
		if self.ocount < self.icount:
			self.ocount += 1

	def _sendCommand(self, cmd):
		"""
		Send a raw command to katago.

		Increase input counter. As on each gtp command, KataGo is expected 
		to ouput '=\n\n' we wait for 2 lines of ouput.
		"""
		if not self._ON: pass
		else:
			# print("Sending command:", cmd)
			cmd += "\n"
			os.write(self.stdin, cmd.encode())
			self.icount += 2

	def setBoardsize(self, size):
		"""Set the boardsize of KataGo"""
		self._sendCommand("boardsize {}".format(size))

	def setKomi(self, komi):
		"""Set the komi of KataGo"""
		self._sendCommand("komi {}".format(komi))

	def playStone(self, pla, txt):
		"""play a stone on intersection corresponding to 'txt'"""
		player = {Board.BLACK: "B", Board.WHITE: "W"}
		cmd = "play {} {}".format(player[pla], txt)
		self._sendCommand(cmd)

	def playCoord(self, i, j, pla, size=19):
		"""Play a stone at coordinates (i, j)"""
		txt = coordToStd(i, j, size)
		self.playStone(pla, txt)

	def undo(self):
		"""Undo the previous move"""
		self._sendCommand("undo")

	def clearBoard(self):
		"""Clear the board of KataGo"""
		self._sendCommand("clear_board")

	def clearCache(self):
		"""Clear KataGo's cache"""
		self._sendCommand("clear-cache")

	def stop(self):
		"""Stop what KataGo is doing.

		Use it when you want to stop an analysis currently running."""
		self.searching = False
		self._sendCommand("stop")

	def close(self):
		"""Close KataGo"""
		self._sendCommand("quit")

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
		self.searching = True
		self._sendCommand(cmd)
			

	