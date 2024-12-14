from random import randint

class Cell:
	def __init__(self, x, y, food = 0, has_animal = False):
		self.x = x
		self.y = y
		self.food = food
		self.has_animal = has_animal
	def __eq__(self, cell):
		return self.x == cell.x and self.y == cell.y
	def __str__(self):
		if self.food > 0:
			return '\\#/'
		else:
			return '___'

class Animal:
	def __init__(self, fat, cell = None, gen = None):
		self.gen = gen
		self.fat = fat
		self.cell = cell
	def __str__(self):
		if self.is_alive():
			return '^o^'
		else:
			return 'x_x'
	def is_alive(self):
		return self.fat >= 0
	def eat(self):
		if self.cell.food > 0 and self.is_alive():
			self.fat += 2
			self.cell.food -= 1
	def metabolism(self):
		self.fat -= 1

class Field:
	def __init__(self, size):
		self.size = size
		self.cells = []
		self.animals = []
		for y in range(size):
			line = []
			for x in range(size):
				line.append(Cell(x,y))
			self.cells.append(line)
	def print(self):
		for y in range(self.size):
			line = ''
			for x in range(self.size):
				cell = self.cells[y][x]
				if cell.has_animal:
					animal = self.find_animal(cell)
					if animal != None:
						line += str(animal)
				else:
					line += str(cell)
			print(line)
	def _coor_range(coor):
		_min = coor - 1
		if _min < 0:
			_min = 0
		_max = coor + 1
		if _max >= self.size:
			_max = self.size-1
		return range(_min, _max)
	def __get_item(self, key):
		return self.cells[key]
	def grow_food(self, amount):
		for i in range(amount):
			x = randint(0, self.size-1)
			y = randint(0, self.size-1)
			self.cells[y][x].food += 1
	def put_animals(self, animals):
		for animal in animals:
			free_cell = False
			while not free_cell:
				x = randint(0, self.size-1)
				y = randint(0, self.size-1)
				if self.cells[y][x].has_animal == False:
					free_cell = True
			animal.cell = self.cells[y][x]
			self.animals.append(animal)
			self.cells[y][x].has_animal = True
	def find_animal(self, cell):
		for animal in self.animals:
			if animal.cell == cell:
				return animal
		return None
	def spend_time(self, time):
		for t in range(time):
			for animal in self.animals:
				animal.eat()
				animal.metabolism()

field = Field(10)
field.grow_food(50)

animals = []
for i in range(10):
	animals.append(Animal(2))
field.put_animals(animals)

field.spend_time(3)
field.print()
