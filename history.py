from board import *

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
		print(self.board)
		for child in self.children:
			child.print()

	def setBoard(self, board):
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
		node.setBoard(board)
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