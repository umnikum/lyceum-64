elements = []
with open('elements.txt', 'r') as infile:
	elements = [line.strip() for line in infile]

atoms = {}
formula = input()
length = len(formula)
is_capital = False

for i in range(length):
	if is_capital:
		name = ''
		if formula[i].islower():
			name = formula[i-1:i+1]
			is_capital = False
		else:
			name = formula[i-1]
			if not formula[i].isupper():
				is_capital = False
		if name in elements:
			if not name in atoms.keys():
				atoms[name] = 1
			else:
				atoms[name] += 1
	elif formula[i].isupper():
		is_capital = True
		
name = formula[-1]
if name.isupper() and name in elements:
	if not name in atoms.keys():
		atoms[name] = 1
	else:
		atoms[name] += 1

print(atoms)
