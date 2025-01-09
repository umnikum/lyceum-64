import random


amount = 20

with open('numbers.dat', 'w') as outfile:
	for i in range(amount):
		for j in range(amount):
			outfile.write(str(random.randint(1, amount))+'\t')
		outfile.write('\n')
