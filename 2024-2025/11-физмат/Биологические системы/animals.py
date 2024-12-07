from random import randint

n = 10
def coor_range(coor):
	_min = coor - 1
	if _min < 0:
		_min = 0
	_max = coor + 1
	if _max >= n:
		_max = n-1
	return range(_min, _max)

def single_index(x, y):
	return n*y + x

class Cell:
	def __init__(self, x, y, food, animal = None):
		self.x = x
		self.y = y
		self.food = food
		self.animal = animal

animals = []
class Animal:
	def __init__(self, fat, gen = None):
		self.gen = gen
		self.fat = fat
	def eat(self, food):
		self.fat += 2
	def metabolism(self):
		self.fat -= 1
		if self.fat < 0:
			animals.remove(self)
field = []
for index in range(n*n):
	field.append(Cell(index%n, index//n, 0))

def grow_food(gen_amount):
	for i in range(gen_amount):
		x = randint(0, n-1)
		y = randint(0, n-1)
		field[single_index(x,y)].food += 1


def print_field():
	for y in range(n):
		line = ''
		for x in range(n):
			cell = field[single_index(x,y)]
			if cell.animal != None:
				line += '@'
			elif cell.food > 0:
				line += '#'
			else:
				line += ' '
			line += '\t'
		print(line)

grow_food(n*n//2)
print_field()
