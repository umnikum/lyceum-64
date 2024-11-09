class Piles:
	def __init__(self, s):
		self.values = [17, s]
	def __str__(self):
		return str(self.values)
	
	def turn(self, index):
		if index < 2:
			self.values[index%2]+=1
		else:
			self.values[index%2]*=2
	def turn_back(self, index):
		if index < 2:
			self.values[index%2]-=1
		else:
			self.values[index%2]//=2
	def is_victory(self):
		return sum(self.values)>=255

for s in range(1, 255):
	piles = Piles(s)
	victory = False
	for j in range(4):
		piles.turn(j)
		for i in range(4):
			piles.turn(i)
			if piles.is_victory():
				victory = True
				break
			else:
				piles.turn_back(i)
		if victory:
			print(s)
			break
		else:
			piles.turn_back(j)
	if victory:
		break
