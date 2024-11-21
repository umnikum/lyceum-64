import os
from treasure_map import origin

class Pirate:
	def __init__(self):
		self.path = origin
		self.journey = []
	def sail(self, num):
		if num == 0:
			if not os.path.samefile(self.path, origin):
				self.path = os.path.dirname(self.path)
				print('Dang it, going back bois!')
				self.journey.append(num)
			else:
				print('I a\'in sailing on shore younkey!')
		else:
			island = os.path.join(self.path, str(num))
			if os.path.isdir(island):
				self.path = island
				print('Sailing to: {}'.format(num))
				self.journey.append(num)
			else:
				print('I see nothing here shkiper! Better follow the map!')
		treasure = os.path.join(self.path, 'treasure.txt')
		if os.path.isfile(treasure):
			with open(treasure, 'r') as infile:
				print('Yo ho ho, found it! {}\n{}'.format(infile.readline().strip(), '->'.join(map(str, self.journey))))
			return True
		else:
			return False
	def search(self):
		islands = []
		for dirname in os.path.scandir(path):
			if os.path.isdir(dirname):
				islands.append(int(os.path.basename(dirname)))
		return islands
