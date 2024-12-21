sequence = '9'*81

while sequence.find('33333')>=0 or sequence.find('999')>=0:
	if sequence.find('33333')>=0:
		sequence = sequence.replace('33333', '99', 1)
	else:
		sequence = sequence.replace('999', '3', 1)

print(sequence)
