import sys
import ctypes
import time

from sdl2 import *
from sdl2.sdlttf import *
from math import cos, sin, pi
import sdl2.sdlgfx as gfx

from katago import KataGo
from board import Board, coordToStd
from history import Node
import parser
import sgffiles

DEBUG = False

#
#  Board layout parameters
#

# Cell size, should be odd because the intersection is 1px wide.
CELL_SIZE = 23
# Margin around the goban, in all four directions
MARGIN = 40
# Height of the control area at the bottom
CONTROLS = 100
# Stone radius, should be less than CELL_SIZE // 2
STONE_RADIUS = 10

SHOW_BLACK_HINTS = True
SHOW_WHITE_HINTS = True
SHOW_HEAT_MAP = True
SHOW_VARIATION = True
SHOW_DEAD_STONES = True

# The following are calculated values and not parameters:

# Window width
WIDTH = MARGIN + 19 * CELL_SIZE + MARGIN
# Window height
HEIGHT = MARGIN + 19 * CELL_SIZE + MARGIN + CONTROLS

#
#  Basic colors
#

WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)
GRAY  = lambda x: (x, x, x, 255)

# Hint colors
HINT_COLOR = (240, 240, 5, 255)
# Border color of the best move
PV_COLOR = (255, 0, 0, 255)

# Heat colors
HEAT_RED = (150, 25, 0, 255)
HEAT_BLACK = (25, 25, 25, 255)
def HEAT(x):
	if x == 0: return WHITE
	elif x < 0:
		x = - x
		mr, mg, mb, a = HEAT_BLACK
	else:
		mr, mg, mb, a = HEAT_RED
	r = int(x * mr + (1 - x) * 255)
	g = int(x * mg + (1 - x) * 255)
	b = int(x * mb + (1 - x) * 255)
	return (r, g, b, 255)

#
#  Global data
#

# Parsing informations
args = None

# Last time katago played
ltime = None

# Maximum number of shown hints
HINT_LIMIT = 33

# SDL Renderer
renderer = None

# Texture for black stones
tblackstone = None 
# Texture for white stones
twhitestone = None

# Font for rendering, loaded from a TTF.
font = None
smallfont = None
tinyfont = None
# SDL event for KataGO
SDL_KATAGO = None


# Row names
ROWS = "ABCDEFGHJKLMNOPQRST"

# A class to make input management easier
class Inputs:
	
	def __init__(self):
		self.mousex = None
		self.mousey = None

	# set mouse coordinates
	def setMouse(self, x, y):
		self.mousex, self.mousey = x, y

	# Convert mouse coordinates to board coordinates
	def getCoordinates(self):
		if self.mousex == None or self.mousey == None: return None
		coord = getCoordinates(self.mousex, self.mousey)
		if coord == None: return None
		return coord
#
#  Coordinate abstraction
#  The following functions calculate coordinates.
#

# Intersection coordinates. Rows and columns are counted from 1 to 19.
def inter(row, col):
	half = (CELL_SIZE + 1) // 2
	x = MARGIN + half + CELL_SIZE * (row - 1)
	y = MARGIN + half + CELL_SIZE * (col - 1)
	return (x, y)

def getCoordinates(x, y):
	i = (x - MARGIN) // CELL_SIZE
	j = (y - MARGIN) // CELL_SIZE
	if i < 0 or i >= 19: return None
	if j < 0 or j >= 19: return None
	return j, i


# The rectangle around an intersection.
def cell_rect(row, col):
	half = (CELL_SIZE + 1) // 2
	x, y = inter(row, col)
	return (x - half, y - half, CELL_SIZE, CELL_SIZE)

#
#  Short drawing functions
#  These functions have implicit renderer, font, and wrap SDL_Rect and
#  SDL_Color arguments.
#

# Clears window.
def clear(color):
	SDL_SetRenderDrawColor(renderer, *color)
	SDL_RenderClear(renderer)

# Fills a rectangle.
def fillrect(x, y, width, height, color):
	SDL_SetRenderDrawColor(renderer, *color)
	SDL_RenderFillRect(renderer, SDL_Rect(x, y, width, height))

# Draws a line.
def line(x1, y1, x2, y2, color):
	SDL_SetRenderDrawColor(renderer, *color)
	SDL_RenderDrawLine(renderer, x1, y1, x2, y2)

# Renders text.
# Size of font if specified with the tfont parameter.
# - tfont can be "normal" or "tiny"
# The alignment of the string is specified with the two last parameters:
# - align_x can be "left", "center" or "right"
# - align_y can be "top", "center" or "bottom"
def text(x, y, string, color=BLACK, tfont="normal", align_x="center", align_y="center"):
	
	if tfont == "normal":
		tfont = font
	elif tfont == "tiny":
		tfont = tinyfont
	string = bytes(string, "utf8")
	surface = TTF_RenderText_Blended(tfont, string, SDL_Color(*color))
	texture = SDL_CreateTextureFromSurface(renderer, surface)

	w = surface.contents.w
	h = surface.contents.h

	if align_x == "center":
		x -= w // 2
	if align_x == "right":
		x -= w
	if align_y == "center":
		y -= h // 2
	if align_y == "bottom":
		y -= h

	SDL_RenderCopy(renderer, texture, None, SDL_Rect(x, y, w, h))
	SDL_FreeSurface(surface)
	SDL_DestroyTexture(texture)

# Draws a circle, because gfx's filledCircle is terrible.
def circle(cx, cy, radius, color):
	SDL_SetRenderDrawColor(renderer, *color)

	x = 0
	y = radius
	m = 5 - 4 * radius

	while x <= y:
		line(cx - x, cy + y, cx + x, cy + y, color)
		line(cx - y, cy + x, cx + y, cy + x, color)
		line(cx - x, cy - y, cx + x, cy - y, color)
		line(cx - y, cy - x, cx + y, cy - x, color)

		if m > 0:
			y -= 1
			m -= 8 * y
		x += 1
		m += 8 * x + 4

# Draw a triangle.
def triangle(cx, cy, radius, color):
	SDL_SetRenderDrawColor(renderer, *color)

	rcospi = int(radius*cos(pi/6))
	rsinpi = int(radius*sin(pi/6))
	line(cx, cy - radius, cx + rcospi, cy + rsinpi, color)
	line(cx + rcospi, cy + rsinpi, cx - rcospi, cy + rsinpi, color)
	line(cx - rcospi, cy + rsinpi, cx, cy - radius, color)

# Draws a stone. The owner can be either "black" or "white".
# - param - mode is "texture" or "draw". If to "texture", use tblackstone
#   and twhitestone to draw the stone. Otherwise, draw directly the stone.
def stone(x, y, owner, mode="texture"):

	if mode == "texture":
		if owner == "black" and tblackstone != None:
			w, h = 2*STONE_RADIUS, 2*STONE_RADIUS
			x, y = x - w//2, y - w//2
			SDL_RenderCopy(renderer, tblackstone, None, SDL_Rect(x, y, w+1, h+1))
			return None
		if owner == "white" and twhitestone != None:
			w, h = 2*STONE_RADIUS, 2*STONE_RADIUS
			x, y = x - w//2, y - w//2
			SDL_RenderCopy(renderer, twhitestone, None, SDL_Rect(x, y, w+1, h+1))
			return None	

	main, border = (BLACK, WHITE) if owner == "black" else (WHITE, BLACK)
	r = STONE_RADIUS

	if owner == "white":
			circle(x, y, r, border)

	circle(x, y, r-2, main)
	gfx.aacircleRGBA(renderer, x, y, r-2, *main)
	gfx.aacircleRGBA(renderer, x, y, r-1, *border)
	gfx.aacircleRGBA(renderer, x, y, r, *border)

# Create the texture for a black stone
# - param - color is either "black" or "white" to accordingly initialize
# tblackstone and twhitestone.
def createStoneTexture(color):

	if color == "black":
		global tblackstone
		tblackstone = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_RGBA8888,
			SDL_TEXTUREACCESS_TARGET, STONE_RADIUS*2+1, STONE_RADIUS*2+1)
		SDL_SetRenderTarget(renderer, tblackstone)
		SDL_SetTextureBlendMode(tblackstone, SDL_BLENDMODE_BLEND)
		SDL_SetRenderDrawColor(renderer, *(255, 255, 255, 0))
		SDL_RenderFillRect(renderer, None)
		stone(STONE_RADIUS, STONE_RADIUS, "black", mode="draw")
		SDL_SetRenderTarget(renderer, None)
	
	if color == "white":
		global twhitestone
		SDL_SetRenderDrawColor(renderer, *(255, 255, 255, 0))
		twhitestone = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_RGBA8888,
			SDL_TEXTUREACCESS_TARGET, STONE_RADIUS*2+1, STONE_RADIUS*2+1)
		SDL_SetRenderTarget(renderer, twhitestone)
		SDL_SetTextureBlendMode(twhitestone, SDL_BLENDMODE_BLEND)
		SDL_SetRenderDrawColor(renderer, *(255, 255, 255, 0))
		SDL_RenderFillRect(renderer, None)
		stone(STONE_RADIUS, STONE_RADIUS, "white", mode="draw")
		SDL_SetRenderTarget(renderer, None)

	# SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND)

def destroyStoneTexture(color="black"):
	
	if color == "black":
		global tblackstone
		SDL_DestroyTexture(tblackstone)
	if color == "white":
		global twhitestone
		SDL_DestroyTexture(twhitestone)


def circ_mark(x, y, owner):
	main, border = (BLACK, WHITE) if owner == "black" else (WHITE, BLACK)
	r = STONE_RADIUS // 2
	gfx.aacircleRGBA(renderer, x, y, r, *border)

# Draw the score diagram
# - scores - list of scores (should be color-constant)
def drawScoreList(scores):
	if len(scores) <= 1: return None
	if not SHOW_BLACK_HINTS or not SHOW_WHITE_HINTS: return None

	GLOW_WHITE = (255, 255, 255, 125)
	srWidth = WIDTH//2
	srHeight = CONTROLS	
	fillrect(0, HEIGHT - CONTROLS + 1, srWidth, CONTROLS, GRAY(50))
	m = min(-5, min(scores)) - 1
	M = max(5, max(scores)) + 1
	num = len(scores)
	dx = srWidth / (num - 1)

	x = 0
	prevx = None
	prevy = None

	middle = int(HEIGHT - CONTROLS * m / (m - M) + 1)
	line(0, middle, srWidth, middle, GRAY(192))

	five = 5 * (m // 5)
	while five <= M:
		l = (five - m) / (M - m)
		y = int(HEIGHT - CONTROLS * l + 1)
		line(0, y, srWidth, y, GLOW_WHITE)
		five += 5

	for i, score in enumerate(scores):
		l = (score - m) / (M - m)
		y = int(HEIGHT - CONTROLS * l + 1)
		x = int(i * dx)
		if prevx != None:
			delta = (y - prevy) / dx
			v = prevy
			for u in range(prevx, x):
				line(u, middle, u, int(v), GLOW_WHITE)
				v += delta	 
			# line(prevx, prevy, x, y, GRAY(0))
		prevx, prevy = x, y


# Draw a sequence of moves
# - moves - ordered coordinates list
# - pla - player playing first in the sequence
def draw_moves(moves, pla, limit=99):
	getowner = lambda c: "black" if c == Board.BLACK else "white"
	getcolor = lambda c: WHITE if c == Board.BLACK else BLACK 
	for i, (col, row) in enumerate(moves):
		if i >= limit: break
		col, row = col + 1, row + 1
		stone(*inter(row, col), getowner(pla), mode="texture")
		if i < 9:
			text(*inter(row, col), str(i+1), color=getcolor(pla))
		else:
			text(*inter(row, col), str(i+1), color=getcolor(pla), tfont=smallfont)
		pla = Board.getOpponent(pla)

# Mark dead stones. Stones are marked according to the heat map.
# A stone is considered probably dead if it is landing in the opponent's 
# teritory.
# board - a board object
def draw_dead_stones(board):
	for row in range(1, 20):
		for col in range(1, 20):
			owner = board.stones[col-1][row-1]
			p = board.deadValue(row-1, col-1)
			if p > 0:
				color = WHITE if owner == Board.BLACK else BLACK
				radius = int((1 + p) * STONE_RADIUS // 3)
				triangle(*inter(row, col), radius, color)

# Draw a inting stone
# - intensity - for the alpha-transparency
# - isFirst - set to Trye to draw a thick read border
def hint_stone(x, y, intensity=0.5, isFirst=False):
	r, g, b, a = HINT_COLOR
	a = int(255 * intensity)
	main = r, g, b, a
	border = PV_COLOR if isFirst else HINT_COLOR
	
	r = STONE_RADIUS
	circle(x, y, r-2, main)
	gfx.aacircleRGBA(renderer, x, y, r-2, *main)
	gfx.aacircleRGBA(renderer, x, y, r-1, *border)
	gfx.aacircleRGBA(renderer, x, y, r, *border)
	if isFirst: gfx.aacircleRGBA(renderer, x, y, r+1, *border)

# Adjust a string representing an integer to be 3 characters.
# e.g 1028 becomes 1.0k
# e.g 208512 becomes 0.2M
def adjustStr(txt):
	e = len(txt)
	if e <= 2: return txt
	if e == 3: return "0.{}k".format(txt[0])
	if e == 4: return "{}.{}k".format(txt[0], txt[1])
	if e == 5: return "{}{}k".format(txt[0], txt[1])
	if e == 6: return "0.{}M".format(txt[0]) 
	if e == 7: return "{}.{}M".format(txt[0], txt[1])
	if e == 8: return "{}{}M".format(txt[0], txt[1])
	if e == 9: return "0.{}G".format(txt[0]) 
	else: return "Lolwut did you truly made this many visits ?"

# Draw hint_informations - number of visits and score expectation
def hint_info(x, y, visits, score):
	visitstr = str(visits)
	if score > 0: scorestr = "+{:.0f}".format(score)
	else: scorestr = "-{:.0f}".format(-score)
	text(x, y-5, adjustStr(visitstr), tfont="tiny")
	text(x, y+5, scorestr, tfont="tiny")

#
#  Hint rendering function
#

def render_hints(pv, turn, board, coord=None):

	if turn == Board.BLACK and not SHOW_BLACK_HINTS:
		return None
	if turn == Board.WHITE and not SHOW_WHITE_HINTS:
		return None

	global SHOW_VARIATION
	SHOW_VARIATION = SHOW_BLACK_HINTS and SHOW_WHITE_HINTS

	maxVisits = 0
	for visits, _, _, _, _ in pv:
		maxVisits = max(maxVisits, visits)
	if maxVisits == 0: maxVisits = 1

	drawnSeq = False
	for _, _, _, _, moves in pv:
		i, j = moves[0]
		if moves[0] == coord and board.stones[i][j] == Board.EMPTY:
			if SHOW_VARIATION: 
				# Show the whole sequence only if 'show_variation' is on
				draw_moves(moves, turn)
			else:
				# Else, just draw one move
				draw_moves([moves[0]], turn)
			drawnSeq = True

	if drawnSeq: return None

	isFirst = True
	for i, (visits, winrate, scoreMean, scoreStDev, moves) in enumerate(pv):
		if i >= HINT_LIMIT: break
		col, row = moves[0]
		if board.stones[col][row] != Board.EMPTY: continue
		hint_stone(*inter(row+1, col+1), intensity=visits/maxVisits, isFirst=isFirst)
		if SHOW_BLACK_HINTS and SHOW_WHITE_HINTS:
			hint_info(*inter(row+1, col+1), visits, scoreMean)
		isFirst = False

#
#  Board rendering function
#

def render(board, history, coord=None):

	## Getting informations
	# - pla : color of current player 
	# - pv : principal variation_S_ information
	# - lmove : coordinates of last move (None of none)
	pla = history.getTurn()
	pv = history.getPV()
	lmove = history.getLastMove()

	## Clear the board - draw mondain rectangles and text
	clear(WHITE)
	fillrect(0, HEIGHT - CONTROLS + 1, WIDTH, CONTROLS, GRAY(192))

	text(3 * WIDTH // 4, HEIGHT - CONTROLS // 2, "KataGo Analyzer", BLACK)

	## Heat map
	if SHOW_HEAT_MAP:
		for row in range(1, 20):
			for col in range(1, 20):
				fillrect(*cell_rect(row, col), HEAT(board.heat[row-1][col-1]))

	## Goban lines - Hoshi
	for i in range(1, 20):
		line(*inter(1, i), *inter(19, i), GRAY(128))
		line(*inter(i, 1), *inter(i, 19), GRAY(128))
	for i in [4, 10, 16]:
		for j in [4, 10, 16]:
			x, y = inter(i, j)
			circle(x, y, 3, GRAY(128))
	# Goban boundary
	line(*inter(1, 1),  *inter(1, 19),  BLACK)
	line(*inter(1, 19), *inter(19, 19), BLACK)
	line(*inter(1, 1),  *inter(19, 1),  BLACK)
	line(*inter(19, 1), *inter(19, 19), BLACK)
	# Coordinates
	for i in range(1, 20):
		x, y = inter(i, 1)
		text(x, y - 24, ROWS[i-1], BLACK, align_x="center", align_y="bottom")
		x, y = inter(i, 19)
		text(x, y + 24, ROWS[i-1], BLACK, align_x="center", align_y="top")
		x, y = inter(1, i)
		text(x - 32, y, str(20-i), BLACK, align_x="center", align_y="center")
		x, y = inter(19, i)
		text(x + 32, y, str(20-i), BLACK, align_x="center", align_y="center")


	## Stones
	for row in range(1, 20):
		for col in range(1, 20):
			st = board.stones[col - 1][row - 1]

			if st == Board.BLACK:
				stone(*inter(row, col), "black", mode="texture")
			elif st == Board.WHITE:
				stone(*inter(row, col), "white", mode="texture")

	## Mark last move
	if lmove:
		pla, col, row = lmove
		owner = "black" if pla == Board.BLACK else "white"
		circ_mark(*inter(row+1, col+1), owner)

	## Rendering Hints & variations & score diagram
	if SHOW_DEAD_STONES: draw_dead_stones(board)
	render_hints(pv, board=board, turn=history.getTurn(), coord=coord)
	if SHOW_WHITE_HINTS and SHOW_BLACK_HINTS: 
		drawScoreList(history.getScoreSeq())
	
	SDL_RenderPresent(renderer)

## Init board, katago and history
# SDL_KATAGO - SDL event corresponding to KataGo's analysis
# path - optional parameter to import a sgf file
def init(SDL_KATAGO, path=None, skatago=True):

	## Standard
	if not path:
		board = Board(size=19)
		kata = KataGo(SDL_KATAGO, turnoff=not skatago)
		history = Node(kata)
		history._getRoot().setBoard(board, current=False)
		kata.setBoardsize(19)
		kata.setKomi(7.5)

	## Importing a sgf file
	else:
		print("Loading {} ...".format(path))
		gdata, setup, moves, rules = sgffiles.load_sgf_moves(path)

		board = Board(size=gdata.size)
		kata = KataGo(SDL_KATAGO, turnoff=not skatago)
		history = Node(kata)
		history._setCurrentBoard(board)
		kata.setBoardsize(gdata.size)
		kata.setKomi(gdata.komi)

		# Setting setup stones
		for pla, i, j in setup:
			history.playMove(board, i, j, pla, analyse=False)
		board = history.getCurrentBoard()
		history = history.setRootHere()
		
		for pla, i, j in moves:
			if (i, j) == (-1, -1): break
			history.playMove(board, i, j, pla, transmit=False)
		history.goToRoot()
		board = history.getCurrentBoard()
		print("{} loaded successfully.".format(path))

	return board, kata, history

# Treat an input
# - event : last SDL_event
# - board : game board
# - kata : KataGo object
# - history : Historic
# - input : Input object
# Output is a tuple (srun, srender)
# - srun : is set to True if the app has to be stoped
# - srender : is set to True if the app has to be re-rendered
# Caution: the board is not always modified. You MUST re-get it with a 
# board = history.getCurrentBoard()
def treatInput(event, board, kata, history, inputs):

	global SHOW_BLACK_HINTS
	global SHOW_WHITE_HINTS
	global SHOW_HEAT_MAP
	global SHOW_DEAD_STONES
	global ltime

	srun, srender = True, False
	if event.type == SDL_QUIT:
		if DEBUG: print("EVENT: quit")
		srun = False

	## KATAGO
	elif event.type == SDL_KATAGO:
		if kata.lastAnalyse:
			if DEBUG: print("Event: katago")
			infos, heatInfos = kata.lastAnalyse
			
			heatInfos = Board.getSign(history.getTurn(current=True)) * heatInfos
			history.updPV(infos)
			board.loadHeatFromArray(heatInfos)
			srender = True

			if args.play:
				move = autoplay(history)
				if move != None:
					i, j = move
					history.setBoard(board, current=True) # save current board
					turn = history.getTurn()
					history.playMove(board, i, j, turn, transmit=True, analyse=True)
					board = history.getCurrentBoard()
					srender = True
					ltime = time.time()
				

	## KEYBOARD - always render
	elif event.type == SDL_KEYDOWN:
		if DEBUG: print("EVENT: KEY DOWN")
		srender = True
		if event.key.keysym.sym == SDLK_RIGHT:
			history.setBoard(board, current=True) # save current board
			board = history.goForward(transmit=True, analyse=True)
			if board == None:
				board = history.getCurrentBoard()
			ltime = time.time() + 1e6

		elif event.key.keysym.sym == SDLK_LEFT:
			history.setBoard(board, current=True) # save current board
			board = history.undo(transmit=True, analyse=True)
			ltime = time.time() + 1e6

		elif event.key.keysym.sym == SDLK_w:
			SHOW_WHITE_HINTS = not SHOW_WHITE_HINTS

		elif event.key.keysym.sym == SDLK_b:
			SHOW_BLACK_HINTS = not SHOW_BLACK_HINTS

		elif event.key.keysym.sym == SDLK_h:
			SHOW_HEAT_MAP = not SHOW_HEAT_MAP

		elif event.key.keysym.sym == SDLK_d:
			SHOW_DEAD_STONES = not SHOW_DEAD_STONES

		elif event.key.keysym.sym == SDLK_g:
			path = input("Write into: ")
			if path != "":
				try:
					txt = history.getSeqToCurrent()
					myfile = open(path, "a+")
					print(txt, file=myfile)
					myfile.close()
					print("Written description at {}".format(path))
					srender = False
				except:
					if DEBUG: print("Error wile trying to write informations in {}".format(path))
			else:
				print("Aborted.")

		elif event.key.keysym.sym == SDLK_l:
			path = input("Path to moves data: ")
			history.loadFileSequences(path)

		elif event.key.keysym.sym == SDLK_SPACE:
			history.loadNextSeq()

		elif event.key.keysym.sym == SDLK_BACKSPACE:
			history.loadPrevSeq()

		else: # If the key is not supported, do not render
			srender = False
			
	## MOUSE MOTION - do not always render
	elif event.type == SDL_MOUSEMOTION:
		lastCoord = inputs.getCoordinates()
		
		x, y = ctypes.c_int(0), ctypes.c_int(0)
		buttonState = SDL_GetMouseState(ctypes.byref(x), ctypes.byref(y))
		x, y = x.value, y.value

		inputs.setMouse(x, y)
		coord = inputs.getCoordinates()
			
		# Check if we need to render
		# Be cautious there otherwise we will rerender each time the mouse
		# moves
		if lastCoord == None: lastCoord = -2, -2
		if coord == None: coord = -2, -2
		lastmoveInfo = history.getMoveInfo(*lastCoord)
		moveInfo = history.getMoveInfo(*coord)
		if (lastmoveInfo != None or moveInfo != None) and lastCoord != coord:
			srender = True
			if DEBUG: print("EVENT: Taking account of motion")

	## MOUSE BUTTONS 
	elif event.type == SDL_MOUSEBUTTONDOWN:
		if DEBUG: print("EVENT: mouse button")
		lastCoord = inputs.getCoordinates()
		if event.button.button == SDL_BUTTON_LEFT:
			if lastCoord != None:
				i, j = lastCoord
				history.setBoard(board, current=True) # save current board
				try:
					turn = history.getTurn()
					history.playMove(board, i, j, turn, transmit=True, analyse=True)
					board = history.getCurrentBoard()
					srender = True
					ltime = time.time()
				except:
					print("This move is illegal")
		elif event.button.button == SDL_BUTTON_RIGHT:
			srender = True
			history.setBoard(board, current=True) # save current board
			board = history.undo(transmit=True, analyse=True)
			ltime = time.time() + 1e6

	return srun, srender


def autoplay(history):
	"""
	If auto is on, return the best move according the history after a thinking
	time kttime. If KataGo is still supposed to thinking, return None.
	- param - auto
	"""

	auto = args.play
	kttime = args.kttime

	if ltime == None: return None

	kturn = Board.BLACK if auto == "black" else Board.WHITE
	cturn = history.getTurn(current=True)
	if kturn != cturn: return None

	t = time.time()
	if t - ltime < kttime: return None

	pv = history.getPV(current=True)
	visits, winrate, scoreMean, scoreStDev, moves = pv[0]
	bestmove = moves[0]
	return bestmove 

# Main function
# run the katago-analyzer app.

def run():

	global args
	args = parser.parse_args()

	path = args.sgffile
	skatago = args.skatago
	silent = args.silent
	auto = args.play
	kttime = args.kttime

	if auto:
		print("KataGo playing {} thinking {} seconds".format(auto, kttime))
		global ltime
		ltime = time.time()

	if silent:
		global SHOW_BLACK_HINTS
		global SHOW_WHITE_HINTS
		global SHOW_HEAT_MAP
		global SHOW_VARIATION
		global SHOW_DEAD_STONES
		SHOW_BLACK_HINTS = False
		SHOW_WHITE_HINTS = False
		SHOW_HEAT_MAP = False
		SHOW_VARIATION = False
		SHOW_DEAD_STONES = False

	global font
	global smallfont
	global tinyfont
	global renderer
	global SDL_KATAGO

	SDL_Init(SDL_INIT_VIDEO)
	TTF_Init()

	window = SDL_CreateWindow("KataGo Analyzer".encode(),
		SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
		WIDTH, HEIGHT, SDL_WINDOW_SHOWN)
	renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED)
	font = TTF_OpenFont(b"DejaVuSans.ttf", 13)
	smallfont = TTF_OpenFont(b"DejaVuSans.ttf", 10)
	tinyfont = TTF_OpenFont(b"DejaVuSans.ttf", 7)
	createStoneTexture("black")
	createStoneTexture("white")

	SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, b'1')

	# Creating SDL_Events for Katago
	SDL_KATAGO = SDL_RegisterEvents(1)

	# Initialise board & katago & inputs
	board, kata, history = init(SDL_KATAGO, path, skatago)
	inputs = Inputs()

	event = SDL_Event()	
	render(board, history)
	t = None
	while True:
		if t != None:
			dt = time.time() - t
			fps = 1 / dt
			# print("FPS:", fps)
		# Event loop
		SDL_WaitEvent(event)
		t = time.time()
		srun, srender = treatInput(event, board, kata, history, inputs)
		if not srun: break
		if srender:
			if DEBUG: print("########### Rendering !")
			board = history.getCurrentBoard()
			render(board, history, inputs.getCoordinates())

	print("Closing KataGo")
	kata.close()
	print("Katago closed, closing everything else")
	SDL_DestroyRenderer(renderer)
	SDL_DestroyWindow(window)
	destroyStoneTexture("black")
	destroyStoneTexture("white")
	SDL_Quit()
