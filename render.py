import sys
import ctypes
import sgffiles
from katago import KataGo
from board import Board, coordToStd
from history import Node
from sdl2 import *
from sdl2.sdlttf import *
import sdl2.sdlgfx as gfx
from math import cos, sin, pi
import time
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

# Maximum number of shown hints
HINT_LIMIT = 10

# SDL Renderer
renderer = None
# Font for rendering, loaded from a TTF.
font = None
tinyfont = None

# Row names
ROWS = "ABCDEFGHJKLMNOPQRST"

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
def stone(x, y, owner):
	main, border = (BLACK, WHITE) if owner == "black" else (WHITE, BLACK)
	r = STONE_RADIUS

	if owner == "white":
			circle(x, y, r, border)

	circle(x, y, r-2, main)
	gfx.aacircleRGBA(renderer, x, y, r-2, *main)
	gfx.aacircleRGBA(renderer, x, y, r-1, *border)
	gfx.aacircleRGBA(renderer, x, y, r, *border)

def circ_mark(x, y, owner):
	main, border = (BLACK, WHITE) if owner == "black" else (WHITE, BLACK)
	r = STONE_RADIUS // 2
	gfx.aacircleRGBA(renderer, x, y, r, *border)


# Draw a sequence of moves
def draw_moves(moves, pla, limit=25):
	getowner = lambda c: "black" if c == Board.BLACK else "white"
	getcolor = lambda c: WHITE if c == Board.BLACK else BLACK 
	for i, (col, row) in enumerate(moves):
		col, row = col + 1, row + 1
		stone(*inter(row, col), getowner(pla))
		text(*inter(row, col), str(i+1), color=getcolor(pla))
		pla = Board.getOpponent(pla)

# Mark dead stones
def draw_dead_stones(board):
	for row in range(1, 20):
		for col in range(1, 20):
			owner = board.stones[col-1][row-1]
			p = board.deadValue(row-1, col-1)
			if p > 0:
				color = WHITE if owner == Board.BLACK else BLACK
				radius = int((1 + p) * STONE_RADIUS // 3)
				triangle(*inter(row, col), radius, color)

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

def hint_info(x, y, visits, score):
	visitstr = str(visits)
	if score > 0: scorestr = "+{:.0f}".format(score)
	else: scorestr = "-{:.0f}".format(-score)
	text(x, y-5, adjustStr(visitstr), tfont="tiny")
	text(x, y+5, scorestr, tfont="tiny")

#
#  Hint rendering function
#

def render_hints(pv, turn, coord=None):

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
		if moves[0] == coord:
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
		hint_stone(*inter(row+1, col+1), intensity=visits/maxVisits, isFirst=isFirst)
		hint_info(*inter(row+1, col+1), visits, scoreMean)
		isFirst = False

#
#  Board rendering function
#

def render(board, history, coord=None):

	# Getting informations
	pla = history.getTurn()
	pv = history.getPV()
	lmove = history.getLastMove()

	clear(WHITE)
	fillrect(0, HEIGHT - CONTROLS + 1, WIDTH, CONTROLS, GRAY(192))

	text(WIDTH // 2, HEIGHT - CONTROLS // 2, "KataGo Analyzer", BLACK)

	# Heat map
	if SHOW_HEAT_MAP:
		for row in range(1, 20):
			for col in range(1, 20):
				fillrect(*cell_rect(row, col), HEAT(board.heat[row-1][col-1]))

	for i in range(1, 20):
		line(*inter(1, i), *inter(19, i), GRAY(128))
		line(*inter(i, 1), *inter(i, 19), GRAY(128))

	for i in [4, 10, 16]:
		for j in [4, 10, 16]:
			x, y = inter(i, j)
			circle(x, y, 3, GRAY(128))

	line(*inter(1, 1),  *inter(1, 19),  BLACK)
	line(*inter(1, 19), *inter(19, 19), BLACK)
	line(*inter(1, 1),  *inter(19, 1),  BLACK)
	line(*inter(19, 1), *inter(19, 19), BLACK)

	# Stones
	for row in range(1, 20):
		for col in range(1, 20):
			st = board.stones[col - 1][row - 1]

			if st == Board.BLACK:
				stone(*inter(row, col), "black")
			elif st == Board.WHITE:
				stone(*inter(row, col), "white")

	# Mark last move
	if lmove:
		pla, col, row = lmove
		owner = "black" if pla == Board.BLACK else "white"
		circ_mark(*inter(row+1, col+1), owner)

	for i in range(1, 20):
		x, y = inter(i, 1)
		text(x, y - 24, ROWS[i-1], BLACK, align_x="center", align_y="bottom")
		x, y = inter(i, 19)
		text(x, y + 24, ROWS[i-1], BLACK, align_x="center", align_y="top")
		x, y = inter(1, i)
		text(x - 32, y, str(20-i), BLACK, align_x="center", align_y="center")
		x, y = inter(19, i)
		text(x + 32, y, str(20-i), BLACK, align_x="center", align_y="center")

	# Rendering Hints & variations
	if SHOW_DEAD_STONES: draw_dead_stones(board)
	render_hints(pv, turn=history.getTurn(), coord=coord)

	SDL_RenderPresent(renderer)

# Init board, katago and history

def init(SDL_KATAGO, path=None):

	if not path:
		board = Board(size=19)
		kata = KataGo(SDL_KATAGO)
		history = Node(kata)
		kata.setBoardsize(19)
		kata.setKomi(7.5)

	else:
		gdata, setup, moves, rules = sgffiles.load_sgf_moves(path)

		board = Board(size=gdata.size)
		kata = KataGo(SDL_KATAGO)
		history = Node(kata)
		kata.setBoardsize(gdata.size)
		kata.setKomi(gdata.komi)

		# Setting setup stones
		for pla, i, j in setup:
			history.playMove(board, i, j, pla, analyse=False)
		board = history.getCurrentBoard()
		history = history.setRootHere()
		
		for pla, i, j in moves:
			history.playMove(board, i, j, pla, transmit=False)
		history.goToRoot()
		board = history.getCurrentBoard()

	kata.analyse(ttime=100)

	return board, kata, history

def run():

	# Asking the user to load a game
	path = sys.argv[1] if len(sys.argv) > 1 else None

	SDL_Init(SDL_INIT_VIDEO)
	TTF_Init()

	global font
	global tinyfont
	global renderer
	global SHOW_BLACK_HINTS
	global SHOW_WHITE_HINTS
	global SHOW_HEAT_MAP
	global SHOW_DEAD_STONES

	window = SDL_CreateWindow("KataGo Analyzer".encode(),
		SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
		WIDTH, HEIGHT, SDL_WINDOW_SHOWN)
	renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED)
	font = TTF_OpenFont(b"DejaVuSans.ttf", 13)
	tinyfont = TTF_OpenFont(b"DejaVuSans.ttf", 7)

	SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, b'1')

	# Creating SDL_Events for Katago
	SDL_KATAGO = SDL_RegisterEvents(1)

	# Initialise board & katago
	board, kata, history = init(SDL_KATAGO, path)
	
	running = True
	event = SDL_Event()	
	
	lastCoord = None
	render(board, history)
	while running:
		# Event loop
		
		SDL_WaitEvent(event)
		if event.type == SDL_QUIT:
			running = False
			break
		elif event.type == SDL_KATAGO:
			if kata.lastAnalyse:
				infos, heatInfos = kata.lastAnalyse
				# skip if event key is out of date
				if kata.key != kata.lastEventKey: continue 
				if history.getTurn() == Board.WHITE: heatInfos = -heatInfos
				history.updPV(infos)
				board.loadHeatFromArray(heatInfos)
		elif event.type == SDL_KEYDOWN: # Keyboard
			if event.key.keysym.sym == SDLK_RIGHT:
				history.setBoard(board) # save current board
				board = history.goForward(transmit=True, analyse=True)
				if board == None:
					board = history.getCurrentBoard()
			elif event.key.keysym.sym == SDLK_LEFT:
				history.setBoard(board) # save current board
				board = history.undo(transmit=True, analyse=True)
			elif event.key.keysym.sym == SDLK_w:
				SHOW_WHITE_HINTS = not SHOW_WHITE_HINTS
			elif event.key.keysym.sym == SDLK_b:
				SHOW_BLACK_HINTS = not SHOW_BLACK_HINTS
			elif event.key.keysym.sym == SDLK_h:
				SHOW_HEAT_MAP = not SHOW_HEAT_MAP
			elif event.key.keysym.sym == SDLK_d:
				SHOW_DEAD_STONES = not SHOW_DEAD_STONES
			else: # for performance reasons
				continue
		elif event.type == SDL_MOUSEMOTION:
			x, y = ctypes.c_int(0), ctypes.c_int(0)
			buttonState = SDL_GetMouseState(ctypes.byref(x), ctypes.byref(y))
			x, y = x.value, y.value
			coord = getCoordinates(x, y)
			if not coord: 
				lastCoord = None
				continue # performances !
			else:
				if not lastCoord: lastCoord = coord
				elif lastCoord == coord: continue # performances !
				else:
					lastCoord = coord
		elif event.type == SDL_MOUSEBUTTONDOWN:
			if event.button.button == SDL_BUTTON_LEFT:
				if not lastCoord: continue
				i, j = lastCoord
				history.setBoard(board) # save current board
				try:
					history.playMove(board, i, j, history.getTurn(), transmit=True, analyse=True)
					board = history.getCurrentBoard()
				except:
					print("This move is illegal")
			elif event.button.button == SDL_BUTTON_RIGHT:
				history.setBoard(board) # save current board
				board = history.undo(transmit=True, analyse=True)
			else: # PERFOOOORMANNNNCES 
				continue
		else: # performances +++ 
			continue

		render(board, history, lastCoord)

	print("Closing KataGo")
	kata.close()
	print("Katago closed, closing everything else")
	SDL_DestroyRenderer(renderer)
	SDL_DestroyWindow(window)
	SDL_Quit()
