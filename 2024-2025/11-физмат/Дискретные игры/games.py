def turn_add(index):
	piles[index] += 1

def turn_mult(index):
	piles[index] *= 2

def is_game_over():
	return piles[0]>255 or piles[1]>255

def my_strategy():
	if piles[0] > 127:
		turn_mult(0)
	else:
		if piles[1] > 127:
			turn_mult(1)
		else:
			if piles[0] < piles[1]:
				turn_add(0)
			else:
				turn_add(1) 
		

#for S in range(1, 238):
S = 18;
piles = [17, S]
my_strategy()
print(piles)

