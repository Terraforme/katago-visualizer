import numpy as np

def test():
	b = Board()
	while True:
		print(b)
		cmd = input("= ")
		tokens = cmd.split()
		if tokens[0] == "play":
			if   tokens[1] == "B": pla = Board.BLACK
			elif tokens[1] == "W": pla = Board.WHITE
			else:
				print("Incorrect Command")
				continue
			i, j =stdToCoord(tokens[2])
			try:
				b.playStone(i, j, pla)
			except:
				print("Illegal move")
		#print("Incorrect Command")

def validCoordinates(i, j, size=19):
	"""Return whether (i, j) are valid coordinates or not."""
	if i >= size or j >= size: return False
	if i < 0 or j < 0: return False
	return True

def coordToStd(i, j, size=19):
	"""Convert a move from its coordinates format (i, j) to standard
	format (e.g C15)"""
	letter = Board.ROWS[j]
	num = size - i
	return letter + str(num)

def stdToCoord(txt, size=19):
	"""Convert a move from its standard format to coordinates"""
	j = Board.ROWS.index(txt[0])
	i = size - int(txt[1:])
	return i, j

class Board:
	"""Board for the game of Go

	Goban is modelised using a N*N matrix (it is not linearised).
	Coordinate (i, j) is the i-th intersection counting from left to right
	and j-th one from top to bottom."""

	EMPTY = 0
	BLACK = 1
	WHITE = 2
	BSIGN = 1
	WSIGN = -1
	PASS = -1, -1

	getOpponent = lambda c: Board.WHITE if c == Board.BLACK else Board.BLACK
	getAdj = lambda i, j: [(i+1, j), (i-1, j), (i, j+1), (i, j-1)]
	SIGNSWITCH = lambda s: - s

	ROWS = "ABCDEFGHJKLMNOPQRST"

	def __init__(self, size=19):
		self.size = size
		self.stones = np.zeros(shape=(size, size), dtype="int8")
		self.heat = np.zeros(shape=(size,size))
		self.turn = Board.BLACK

	def copy(self):
		"""Return a copy of the board"""
		size = self.size
		cpy = Board(size=size)
		cpy.stones = self.stones.copy()
		cpy.heat = self.stones.copy()
		return cpy

	def clear(self):
		"""Clear the content of the board"""
		size = self.size
		self.stones = np.zeros(shape=(size, size))
		self.heat = np.zeros(shape=(size,size))

	def clearStones(self):
		"""Clear stones only"""
		size = self.size
		self.stones = np.zeros(shape=(size, size))


	def resize(self, size):
		"""Clear the content of the board and resize it"""
		self.size = size
		self.clear()

	def rotate(self, num=-1):
		self.stones = np.rot90(self.stones, num)
		self.heat = np.rot90(self.heat, -num)

	def setTurn(self, pla):
		"""Set turn"""
		self.turn = pla

	def setStone(self, i, j, pla):
		"""Hard-set a stone at coordinates (i, j)"""
		self.stones[i][j] = pla

	def setSequence(self, moves):
		"""Hard stones on the board"""
		for pla, i, j in moves:
			self.setStone(i, j, pla)

	def playStone(self, i, j, pla=None):
		"""Play a stone a coordinates (i, j)"""
		if not pla: pla = self.turn
		if not self.isLegal(i, j, pla):
			raise(Exception("Move {} is illegal".format(
				coordToStd(i, j, self.size))))
		cap = self.captured(i, j, pla)
		for chain in cap:
			for u, v in chain:
				self.stones[u][v] = Board.EMPTY
		self.setStone(i, j, pla)
		self.turn = Board.getOpponent(pla)

	def captured(self, i, j, pla):
		"""Return the list of captured chains by move i, j"""
		adv = Board.getOpponent(pla)
		adj = Board.getAdj(i, j)
		cap = []
		self.setStone(i, j, pla)
		for u, v in adj:
			if not validCoordinates(u, v, self.size): continue
			if self.stones[u][v] != adv: continue

			if self.chainLiberties(u, v) == 0:
				cap.append(self.getChain(u, v))
		self.setStone(i, j, Board.EMPTY)
		return cap

	def isSuicideMove(self, i, j, pla):
		"""Say whether or not a move is suicide."""
		if self.stones[i][j] != Board.EMPTY: return True
		self.setStone(i, j, pla)
		lib = self.chainLiberties(i, j)
		self.setStone(i, j, Board.EMPTY)
		return lib == 0

	def isLegal(self, i, j, pla):
		"""Return True if move (i, j) is legal, and False otherwise."""
		# FIXME : no KO managment
		if not validCoordinates(i, j, self.size): return False
		if self.stones[i][j] != Board.EMPTY: return False
		cap = self.captured(i, j, pla)
		iss = self.isSuicideMove(i, j, pla)
		if cap == [] and iss: return False
		return True

	def stoneLiberties(self, i, j):
		"""Return the number of liberties of a stone considered single.
		If the stone is not single, forget about the stones it is linked with.
		"""
		num = 0
		adj = Board.getAdj(i, j)
		for u, v in adj:
			if not validCoordinates(u, v, self.size): continue
			if self.stones[u][v] != Board.EMPTY: continue
			num += 1
		return num

	def chainLiberties(self, i, j):
		"""Return the number of liberties of the group at (i, j)"""
		chain = self.getChain(i, j)
		libCount = [self.stoneLiberties(u, v) for u, v in chain]
		return sum(libCount)

	def getChain(self, i, j):
		"""Return the list of all stones linked to (i, j) having the
		same color"""
		N = self.size
		seen = np.zeros(shape=(N,N)) # matrix of False
		color = self.stones[i][j]
		chain = []
		if color == Board.EMPTY: return []

		def getChain_aux(i, j):
			seen[i][j] = True
			if color != self.stones[i][j]: return None

			chain.append((i,j))
			adj = Board.getAdj(i, j)
			for u, v in adj:
				if validCoordinates(u, v, self.size) and not seen[u][v]:
					getChain_aux(u, v)

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

	def __repr__(self):
		size = self.size
		txt = "  "
		for i in range(size):
			txt += " " + Board.ROWS[i]
		txt += "\n"
		for row in range(size):
			txt += "{:2}".format(size-row)
			for col in range(size):
				if   self.stones[row][col] == Board.EMPTY: txt += " ."
				elif self.stones[row][col] == Board.BLACK: txt += " X"
				elif self.stones[row][col] == Board.WHITE: txt += " O"
				else : txt += " ?"
			txt += "\n"
		return txt

	def loadHeatFromArray(self, array):
		"""Load heats from a numpy array"""
		size = self.size
		for row in range(size):
			for col in range(size):
				self.heat[row][col] = - array[col * size + row]
				# FIXME -1 * . is articial

	# miscellaneous

	def render_seq(self, moves):
		"""Render a sequence of moves"""
		for pla, i, j in moves:
			self.playStone(i, j, pla)
			print(self)
