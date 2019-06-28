#!/usr/bin/python3

from matplotlib import pyplot as plt
import numpy as np

def average(data):
    avg = sum(data) / len(data)
    for i in range(len(data)):
        data[i] = avg

def drawLevel(data, label="-"):
    Y = data
    X = np.array([i for i in range(len(data))])
    plt.plot(X, Y, label=label)

def parse(txt):
    lines = txt.split("\n")
    B, W = [], []
    for line in lines:
        tokens = line.split()
        nBlack, nWhite = False, False
        for tok in tokens:
            if nBlack or nWhite:
                value = - float(tok)
            if nBlack: 
                nBlack = False
                B.append(value)
            if nWhite:
                nWhite = False
                W.append(value)
            
            if tok == "BLACK":
                nBlack = True
            if tok == "WHITE":
                nWhite = True
    
    return B, W

def txtFromFile(path):
    myfile = open(path, "r")
    data = myfile.read()
    return data

def autoDraw(path, show=False, label="-", averaged=False, merge=True):
    txt = txtFromFile(path)
    B, W = parse(txt)
    
    if averaged:
        average(B)
        average(W)
    if not merge:
        drawLevel(B, label=label)
        drawLevel(W, label=label)
    else:
        drawLevel((np.array(B)+np.array(W))/2, label=label)
    
    if show: plt.show()

def autoPlot(averaged=True):
    try:
        autoDraw("6d-estimate.txt", label="6d", averaged=averaged)
    except:
        pass
    for i in range(1,20):
        try:
            autoDraw("{}k-estimate.txt".format(i), label="{}k".format(i), 
                averaged=averaged)
        except:
            continue
    plt.legend()
    plt.show()

if __name__ == "__main__":
    pass
