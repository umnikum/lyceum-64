file = open('navigation.dat', 'r')
data = []
for line in file:
	elements = line.split()
	data.append([int(elem) for elem in elements])
file.close()

file = open('cities.dat', 'r')
cities = [line.strip() for line in file]
file.close()

def print_table(data):
	for row in data:
		line = ''
		for elem in row:
			line += str(elem) + '\t'
		print(line, '\n')

def symmetrize(data):
	l = len(data)
	for i in range(l):
		for j in range(i):
			data[i][j] = data[j][i]
	return data


def print_way(way):
	line = str(cities[way[0]])
	for i in range(1, len(way)):
		line += ' -(' + str(data[way[i-1]][way[i]]) + ')-> '+ cities[way[i]]
	print(line)

print_table(symmetrize(data))

way = [0, 1, 2]
print_way(way)


