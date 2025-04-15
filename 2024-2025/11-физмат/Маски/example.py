import re

line = '123*789'
#line = input('Enter mask: ')

mask_s = ''
for c in line:
	if c in '?*':
		mask_s += '.'+c
	else:
		mask_s += c
mask = re.compile(mask_s)

number = '123456789'
#number = '13444789'
for match in mask.finditer(number):
	print('Compatible!')
	break
