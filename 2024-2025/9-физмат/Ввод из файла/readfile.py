with open('input.txt', 'r') as infile:
	for line in infile:
		print(line.strip())

N = 0
arr = []
with open('input.txt', 'r') as infile:
	lines = [line.strip() for line in infile]
	N = int(lines[0])
	for i in range(N):
		arr = [int(lines[i+1]) for i in range(len(lines)-1)]
