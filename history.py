from board import *
from katago import parseLine

TTIME = 100
LVLMUL = 100


def cumulate(a):
	"""Return the averaged cumulation array of a"""
	n = len(a)
	b = [0 for i in range(n)]
	for i in range(n):
		b[i] = (i*b[i-1] + a[i])/(i+1)
	return b

class Node:

	"""
	## PROPERTIES
	Node represent historics. Game historics are rooted and oriented trees.
	By getting a node with 'a = Node()', one can create a root from where one
	can access the whole tree. The structure have the following properties:

	- each node can access the root with '_getRoot()'
	- each node can access its parent with .parent
	- each node can access its children stored in the list `.children`
	- there is a token transmitted in the tree. The node having the token is
	  called "current node" and represents the current position we are at.
	- the root can access the current node at any time with '_getCurrent()'

	## HOW TO USE
	
	One can play a move at the current node with 'playMove()'. If the move is
	new, the history will be added a new node - otherwise, the token is 
	given to the according child. Conversly, one can undo a move with 'undo()'.

	To get the current board, one can use 'getCurrentBoard()'. 

	## ABOUT KATAGO & ANALYSIS

	The historic must be initialised with a KataGo object. This KataGo object
	can be accessed at any time and sent commands - still, the Node class
	already provides methods that don't require you to think about KataGo when
	using it - at least most of the time. The historic also stores some analysis
	informations that KataGo sends. To access the information on the current
	position, one can do

	- getPV() - to get the principal variation on current node with
	  attached analysis values.
	- getCurrentBoard().heat - to get heat informations.
	"""

	def __init__(self, katago):
		self.katago = katago
		self.root = self
		self.current = self
		self.parent = self
		self.children = []
		self.board = None
		self.move = None
		self.pv = []

	def print(self):
		"""Print the whole historic"""
		print(self.board)
		for child in self.children:
			child.print()

	def startAnalyse(self, ttime=TTIME):
		"""Start KataGo's analysis"""
		self._getRoot().katago.stop()
		self._getRoot().katago.analyse(ttime)

	def setBoard(self, board, current=False):
		"""Set the board.
		- current - precise if we should do it on the current node
		if current:
			self._getCurrent().board = board.copy()
		else:
			self.board = board.copy()

	def _setCurrentBoard(self, board):
		"""Copy the current board at 'current'"""
		self._getCurrent().setBoard(board)

	def setRootHere(self):
		"""Set the root.

		Use it this way: node = node.setRootHere()"""
		cur = self._getCurrent()
		cur.root = cur
		cur.parent = cur
		cur._setCurrent(cur)
		return cur

	def _getRoot(self):
		"""Return the root history"""
		cur = self
		while cur != cur.root:
			cur.root = cur.root.root
			cur = cur.root
		self.root = cur # Make sure there is compression
		return cur

	def _getPrevious(self):
		if not self._getCurrent().parent:
			return self._getCurrent()
		return self._getCurrent().parent

	def _getCurrent(self):
		return self.root.current

	def _setCurrent(self, ptr):
		self._getRoot().current = ptr

	def getCurrentBoard(self):
		"""Return the current board"""
		return self._getCurrent().board

	def getLastMove(self):
		return self._getCurrent().move

	def getPrevMove(self):
		return self.parent.move

	def scoreMean(self, absolute=True, normalized=False):
		"""Return the score mean - if absolute is True, return the score of 
		Black. The 'normalized' parameter divied by the scoreStDev to take
		accound of the complexity of the situation.""" 
		pv = self.pv
		if pv == []: return None
		visits, winrate, scoreMean, scoreStDev, moves = pv[0]
		if scoreStDev <= 10: scoreStDev = 10
		turn = self.getTurn(current=False)
		if absolute:
			val = - scoreMean * Board.getSign(turn)
		else:
			val = - scoreMean

		if normalized: 
			return val / scoreStDev
		else:
			return val

	def scoreStdev(self):
		pv = self.pv
		if pv == []: return None
		visits, winrate, scoreMean, scoreStdev, moves = pv[0]
		return scoreStdev

	def getCurrentScoreMean(self):
		"""Return current score according to last analysis"""
		return self._getCurrent().scoreMean()

	def extraInfoStr(self):
		"""Return a string corresponding to the current information.
		Format is such that it can be parsed using katago.parseLine()."""
		pv = self._getCurrent().getPV()
		if pv == None: return ""

		## Normal informations
		txt = ""
		for visits, winrate, scoreMean, scoreStdev, moves in pv:
			txt += "info {} visits {} winrate {} scoreMean {} scoreStdev {} ".format(
				coordToStd(*moves[0]), visits, winrate, scoreMean, scoreStdev)
			txt += "pv "
			for i, j in moves:
				txt += "{} ".format(coordToStd(i, j))

		## Ownership
		txt += "ownership "
		board = self._getCurrent().board
		heat = board.heat
		for i in range(19):
			for j in range(19):
				loc = "{} ".format(heat[j][i])
				txt += loc

		return txt

	def fromSeqTxt(self, txt, format="std"):
		"""Little sister of getSeqToCurrent. Read it for more infos."""
		self.goToRoot(transmit=True)
		board = self._getCurrent().board
		if txt == "": return None

		txt = txt.split("#")
		extrainfos = txt[1]
		print(extrainfos)
		txt = txt[0].split(";")
		for movtxt in txt:
			if movtxt == "": break
			movtxt = movtxt.split(".")
			c = movtxt[0]
			mov = movtxt[1]
			if format == "std":
				c = Board.BLACK if c == "B" else Board.WHITE
				i, j = stdToCoord(mov)
				self.playMove(board, i, j, c, transmit=True, analyse=False)
			else:
				raise Exception("Please finish implementation of fromSeqTxt")

		infos, heatInfos = parseLine(extrainfos)
		self.updPV(infos)
		self.getCurrentBoard().loadHeatFromArray(heatInfos)

		#self.startAnalyse()
		print("Loaded sequence.")

	def getSeqToCurrent(self, format="std"):
		"""Return the sequence of moves to current position in a text format.
		The format is ([pla].[move];)*
		- format : "std" for standard - pla is 'B' or 'W' and move is standard
		and "coord" for coordinates with pla being '1' or '2' and move 
		is coordinates '([row],[col])'. """
		cur = self._getCurrent()
		root = self._getRoot()
		moves = []
		while True:
			if cur.move != None:
				moves.append(cur.move)
			if cur == root or cur == cur.parent: break
			cur = cur.parent
		moves.reverse()

		res = ""
		for pla, i, j in moves:
			if format == "coord": 
				res += "{}.({},{});".format(pla, i, j)
			if format == "std":
				c = "B" if pla == Board.BLACK else "W"
				res += "{}.{};".format(c, coordToStd(i, j))
		
		res += "#" + self.extraInfoStr()
		return res

	def getScoreSeq(self, normalized=False):
		"""Return the list of score from root to current"""
		cur = self._getCurrent()
		root = self._getRoot()
		scores = [0]
		while True:
			score = cur.scoreMean(normalized=normalized)
			if not score: score = scores[-1]
			scores.append(score)
			if cur == root or cur == cur.parent: break
			cur = cur.parent
		
		scores.reverse()
		scores.pop()
		return scores

	def getScoreStdevSeq(self):
		"""Return the list of scoreStDev form root to current"""
		cur = self._getCurrent()
		root = self._getRoot()
		seqStdev = [0]
		while True:
			scoreStdev = cur.scoreStdev()
			if not scoreStdev: scoreStdev = seqStdev[-1]
			seqStdev.append(scoreStdev)
			if cur == root or cur == cur.parent: break
			cur = cur.parent
		
		seqStdev.reverse()
		seqStdev.pop()
		return seqStdev

	def getTurn(self, current=True):
		move = self.getLastMove() if current else self.getPrevMove()
		if not move: return Board.BLACK
		else:
			pla, i, j = move
			return Board.getOpponent(pla)

	def getPV(self):
		"""Return current main variations"""
		return self._getCurrent().pv

	def getMoveInfo(self, i, j, ceil=10):
		"""Return information (if some) on the current move"""
		pvs = self.getPV()
		if pvs == None: return None
		for visits, winrate, scoreMean, scoreStDev, moves in pvs:
			if moves[0] == (i, j):
				return visits, winrate, scoreMean, scoreStDev, moves
		return None

	def updPV(self, pv):
		"""Update current principal variations"""
		self._getCurrent().pv = pv

	def addChild(self, board):
		"""Add a child. 
		If the children already exists, do not add it"""
		for child in self._getCurrent().children:
			if child.board.key == board.key:
				return None
		node = Node(self._getRoot().katago)
		node.parent = self._getCurrent()
		node.root = self._getRoot()
		node.current = self._getCurrent()
		node.setBoard(board, current=False)
		self._getCurrent().children.append(node)
		
	def goForward(self, ttime=TTIME, transmit=True, analyse=True):
		"""Go to the leftmost child. If there is no child, print an error 
		message. Return the corresponding board"""
		if self._getCurrent().children == []: 
			print("No more moves")
		else:
			next = self._getCurrent().children[0]
			self._setCurrent(next)
			pla, i, j = next.move
			if transmit:
				self._getRoot().katago.stop()
				self._getRoot().katago.playCoord(i, j, pla)
				if analyse: self._getRoot().katago.analyse(ttime)
				self._getRoot().katago.key = self.getCurrentBoard().key
			return self.getCurrentBoard()

	def undo(self, ttime=TTIME, transmit=True, analyse=True):
		"""Go to the parent, and return the corresponding board."""
		oldcurrent = self._getCurrent()
		self._setCurrent(self._getCurrent().parent)
		if oldcurrent != self._getCurrent():
			if transmit: 
				self._getRoot().katago.stop()
				self._getRoot().katago.undo()
				if analyse: self._getRoot().katago.analyse(ttime)
				self._getRoot().katago.key = self.getCurrentBoard().key
			return self.getCurrentBoard()
		else:
			return self._getRoot().board

	def playBoard(self, board):
		"""Move to a children. If it does not exists, create it."""
		self.addChild(board)
		for child in self._getCurrent().children:
			if child.board.key == board.key:
				self._setCurrent(child)
				return None

	def playMove(self, board, i, j, pla, transmit=True, analyse=True, ttime=TTIME):
		"""Play a move on a board and add it in the history"""
		
		self._getCurrent().setBoard(board) # save the current board
		board.playStone(i, j, pla)
		if transmit: 
			self._getRoot().katago.stop()
			self._getRoot().katago.playCoord(i, j, pla)
			if analyse: self._getRoot().katago.analyse(ttime=ttime)
		self.playBoard(board)
		self._getRoot().katago.key = self.getCurrentBoard().key
		self._getCurrent().move = pla, i, j
		return self._getCurrent().board

	def goToRoot(self, transmit=False):
		"""Set current as root"""
		cur = self._getCurrent()
		while cur != self._getRoot():
			self.undo(transmit=transmit, analyse=False)
			cur = cur._getPrevious()
		self._setCurrent(self._getRoot())

	def localLoss(self, normalized=True):
		"""Return the loss for current move in history"""
		if self.children == []:
			return None

		nextnode = self.children[0]
		if nextnode.board == None or nextnode.scoreMean() == None:
			return None
		turn = self.getTurn(current=False)
		loss = Board.getSign(turn) * (nextnode.scoreMean() - self.scoreMean())
		pla, i, j = nextnode.move
		print("{} MOVE {} loss: {:.2f}".format(pla, coordToStd(i, j), loss))
		
		return nextnode.scoreMean(normalized=normalized) \
			- self.scoreMean(normalized=normalized)

	def guessLevel(self, lookpla=Board.BLACK, normalized=True, forgetBarrier=0.5):
		"""Guess the level of a player"""
		losses = self.getLossList(lookpla, normalized, forgetBarrier)
		# print("Loss:", np.array(losses))
		return LVLMUL * cumulate(losses)[-1]


	def getLossList(self, lookpla, normalized=True, forgetBarrier=0.5):
		"""Return the list of losses for a player"""
		scores = self.getScoreSeq(normalized=False)
		stdev = self.getScoreStdevSeq()
		# print("scores:", np.array(scores), "\nstdev:", np.array(stdev))
		pla = self.getTurn() if len(scores) % 2 == 1 \
			else Board.getOpponent(self.getTurn())
		if len(scores) < 2: return None
		
		losses = []
		for i in range(len(scores)-1):
			loss = scores[i+1] - scores[i]
			norm = stdev[i]
			if abs(loss) < forgetBarrier: loss = 0
			if normalized: loss /= norm   # normalize loss
			coloredloss = loss * Board.getSign(pla)
			if pla == lookpla:
				losses.append(coloredloss)
			pla = Board.getOpponent(pla)

		return losses