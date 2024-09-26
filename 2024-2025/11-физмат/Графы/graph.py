file = open('navigation.txt', 'r')
data = []
for line in file:
	elements = line.split()
	data.append([int(elem) for elem in elements])
file.close()

print(data)
