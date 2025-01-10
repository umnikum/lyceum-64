import random

id = 1

class Item:
	def __init__(self, name, price):
		global id
		self.id = id
		id += 1
		self.name = name
		self.price = price
	def __str__(self):
		return str(self.id) + '\t' + self.name + '\t' + str(self.price)

class Entry:
	def __init__(self, item, amount = 1):
		self.item = item
		self.amount = amount
	def __str__(self):
		return str(self.item.id) + '\t' + str(self.amount)

class Supplies:
	def __init__(self, date, entries = []):
		self.date = date
		self.entries = entries
	def __str__(self):
		result = ''
		for entry in self.entries:
			result += str(entry) + '\t' + self.date + '\n'
		return result

items = [Item('Ёлочный шарик', 20.0), Item('Гирлянда', 400.0), Item('Мандарины 1кг', 350.0), Item('Коробка конфет', 600.0), Item('Ёлка', 2000.0), Item('Пельмени 1кг', 650.0), Item('Кастрюля', 3500.0), Item('Яблоки 1кг', 150.0), Item('Картофель 1кг', 60.0), Item('Макароны', 200.0)]

with open('items.dat', 'w') as outfile:
	for item in items:
		outfile.write(str(item)+'\n')

supp_amount = random.randint(5, 10)
with open('supplies.dat', 'w') as oufile:
	for supp in range(supp_amount):
		date = str(random.randint(1, 25)) + '.' + str(random.randint(1,12)) + '.2024'
		supplies = Supplies(date)
		for i in range(random.randint(50, 100)):
			supplies.entries.append(Entry(random.choice(items), random.randint(1, 1000)))
		oufile.write(str(supplies))
