file = open('navigation.txt', 'r')
data = []
for line in file:
	elements = line.split()
	data.append([int(elem) for elem in elements])
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

print_table(symmetrize(data))
