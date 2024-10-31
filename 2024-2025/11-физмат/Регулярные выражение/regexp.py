import re

date_pattern = re.compile(r'[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{2,4}')

line = input()

for match in date_pattern.finditer(line):
	begin, end = match.span()
	print(line[begin:end])

