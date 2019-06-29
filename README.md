# katago-visualizer

A python tool to visualize the game of Go from Katago's perspective.

## KataGo, what is this ?

KataGo is a recent engine achieving state of the art level. Unlike LeelaZero,
it can compute something else than winrate out-of-the-box. KataGo natively 
computes board's ownership, a score estimation (in points), and an estimator of 
its confidence in addition to the winrate. Checkout the github reposit
https://github.com/lightvector/KataGo. 

KataGo deserves to have its own GUI application, shaped specifically for him.
With *KataGo Visualizer*, you can explore the game of Go with an estimation 
of the score, of deadstones, or even the skills of players. It is still a 
baby-staged project, so expect to have much more features in the future.

**Remark:**

KataGo's principal variation length is hard-caped in the source code.
If you want more than 10 moves in variations, open the `cpp/gtp.cpp` file,
go to the `analyze()` function and change 

```
static const int analysisPVLen = 9;
```

into 

```
static const int analysisPVLen = 99;
``` 

and you have some room.

## Usage

Run the `main.py` file to run KataGo-Analyzer. You need KataGo binaries
and a model to benefit from KataGo's analysis.
If you specify a path to a sgf file, the lattest will be loaded.

- Press `h` to switch on/off ownership rendering
- Press `d` to switch on/off dead stones guessing
- Press `b` to switch on/off black's hints
- Press `w` to switch on/off white's hints
- Press `g` to generate the sequence to current position into `test.log`
- Press `l` to load a sequence from a file
- Press `space` to load the next position from loaded sequences
- Press `backspace` to load the previous position from loaded sequences. 

Use arrows keys and mouse to navigate in the app.