import sys
import ctypes
from sdl2 import *
import sdl2.sdlgfx as sdlgfx

WIDTH = 700
HEIGHT = 600

def run():

	SDL_Init(SDL_INIT_VIDEO)

	window = SDL_CreateWindow("KataGo Analyser".encode(), 
		SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, 
		WIDTH, HEIGHT, SDL_WINDOW_SHOWN)
	renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED)

	running = True
	event = SDL_Event()
	while running:
		# Event loop
		while SDL_PollEvent(ctypes.byref(event)) != 0:
			if event.type == SDL_QUIT:
				running = False
				break
		# Rendering
		SDL_SetRenderDrawColor(renderer, 255, 255, 255, 255)
		SDL_RenderClear(renderer)
		SDL_RenderPresent(renderer);

	SDL_DestroyRenderer(renderer)
	SDL_DestroyWindow(window)
	SDL_Quit()