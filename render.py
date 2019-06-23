import sys
import ctypes
import sgffiles
from katago import KataGo
from sdl2 import *
from sdl2.sdlttf import *
import sdl2.sdlgfx as gfx
from board import Board
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

# The following are calculated values and not parameters:

# Window width
WIDTH = MARGIN + 19 * CELL_SIZE + MARGIN
# Window height
HEIGHT = MARGIN + 19 * CELL_SIZE + MARGIN + CONTROLS

FPS = 30

#
#  Basic colors
#

WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)
GRAY  = lambda x: (x, x, x, 255)
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

# SDL Renderer
renderer = None
# Font for rendering, loaded from a TTF.
font = None

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
# The alignment of the string is specified with the two last parameters:
# - align_x can be "left", "center" or "right"
# - align_y can be "top", "center" or "bottom"
def text(x, y, string, color, align_x="center", align_y="center"):
	string = bytes(string, "utf8")
	surface = TTF_RenderText_Blended(font, string, SDL_Color(*color))
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

#
#  Board rendering function
#

def render(board):
	clear(WHITE)
	fillrect(0, HEIGHT - CONTROLS + 1, WIDTH, CONTROLS, GRAY(192))

	text(WIDTH // 2, HEIGHT - CONTROLS // 2, "KataGo Analyzer", BLACK)

	# Heat map
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

	for i in range(1, 20):
		x, y = inter(i, 1)
		text(x, y - 24, ROWS[i-1], BLACK, align_x="center", align_y="bottom")
		x, y = inter(i, 19)
		text(x, y + 24, ROWS[i-1], BLACK, align_x="center", align_y="top")
		x, y = inter(1, i)
		text(x - 32, y, str(20-i), BLACK, align_x="center", align_y="center")
		x, y = inter(19, i)
		text(x + 32, y, str(20-i), BLACK, align_x="center", align_y="center")

	SDL_RenderPresent(renderer)

def run():

	# Asking the user to load a game
	path = sys.argv[1] if len(sys.argv) > 1 else input("load: ")
	gdata, setup, moves, rules = sgffiles.load_sgf_moves(path)
	movID = 0
	movnum = len(moves)

	SDL_Init(SDL_INIT_VIDEO)
	TTF_Init()

	global font
	global renderer

	window = SDL_CreateWindow("KataGo Analyzer".encode(),
		SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
		WIDTH, HEIGHT, SDL_WINDOW_SHOWN)
	renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED)
	font = TTF_OpenFont(b"DejaVuSans.ttf", 13)

	SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, b'1')

	# Creating SDL_Events for Katago
	SDL_KATAGO = SDL_RegisterEvents(1)

	# Initialise board & katago
	board = Board(size=gdata.size)
	kata = KataGo(SDL_KATAGO)
	kata.setBoardsize(gdata.size)
	kata.setKomi(gdata.komi)

	# Setting setup stones
	board.setSequence(setup)
	kata.playSeq(setup)

	running = True
	event = SDL_Event()	
	
	kata.analyse(ttime=100)

	while running:
		# Event loop
		
		SDL_WaitEvent(event)
		if event.type == SDL_QUIT:
			running = False
			break
		elif event.type == SDL_KATAGO:
			if kata.lastAnalyse:
				infos, heatInfos = kata.lastAnalyse
				board.loadHeatFromArray(heatInfos)
		elif event.type == SDL_KEYDOWN:
			if event.key.keysym.sym == SDLK_RIGHT:
				if movID >= movnum: pass
				else:
					kata.stop()
					print(moves[movID])
					pla, i, j = moves[movID]
					board.playStone(i, j, pla)
					kata.playCoord(i, j, pla)
					movID += 1
					kata.analyse(ttime=100)
			if event.key.keysym.sym == SDLK_LEFT:
				if movID <= 0: pass
				else:
					kata.stop()
					board.clearStones()
					board.setSequence(setup)
					movID -= 1
					for pla, i, j in moves[:movID]:
						board.playStone(i, j, pla)
					kata.undo()
					kata.analyse(ttime=100)

		render(board)

	print("Closing KataGo")
	kata.close()
	print("Katago closed, closing everything else")
	SDL_DestroyRenderer(renderer)
	SDL_DestroyWindow(window)
	SDL_Quit()
