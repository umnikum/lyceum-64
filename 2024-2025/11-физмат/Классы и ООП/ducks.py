from random import randint

class Bird:
	def __init__(self, name):
		self.name = name
	def talk(self):
		return 0
	def fly(self):
		return 0

class FlyingBird(Bird):
	def fly(self):
		print(self.name, ' Moving into the skies!')


ducks = ['Donald', 'Rubber', 'Malard', 'Krakva', 'Reginald', 'Chriss P. Bacon']
class Duck(FlyingBird):
	def __init__(self):
		_name = randint(0, len(ducks)-1)
		super().__init__(ducks[_name])
	def talk(self):
		print(self.name, ' Quack!')

geese = ['Honker', 'Donker', 'Geronimo', 'Hissper']
class Goose(FlyingBird):
	def __init__(self):
		_name = randint(0, len(geese)-1)
		super().__init__(geese[_name])
	def talk(self):
		print(self.name, ' Gawk!')

ostriges = ['Toby', 'Tony', 'Tiny', 'Tolly', 'Tommy', 'Timmy']
class Ostrige(Bird):
	def __init__(self):
		_name = randint(0, len(ostriges)-1)
		super().__init__(ostriges[_name])
	def talk(self):
		print(self.name, ' Eh eh eh!')
	def fly(self):
		print(self.name, ' Chomping through on foot!')

pond = []
for i in range(randint(10, 20)):
	_type = randint(1, 3)
	if _type == 1:
		pond.append(Duck())
	elif _type == 2:
		pond.append(Goose())
	else:
		pond.append(Ostrige())


item = ''
while item != 'leave':
	item = input()
	for bird in pond:
		if item == 'bread':
			bird.talk()
		else:
			bird.fly()
