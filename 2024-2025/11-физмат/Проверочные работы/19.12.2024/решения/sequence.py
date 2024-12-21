import os


sequence = []
with open(os.path.join('..', 'Вспомогательные файлы', 'Числа.txt'), 'r') as infile:
	sequence = [int(line) for line in infile]
max_1 = 0
for elem in sequence:
	if elem > max_1 and elem%10 == 1:
		max_1 = elem

def condition(subsequence):
	evens = 0
	for elem in subsequence:
		if elem >= max_1:
			return False
		elif elem%2 == 0:
			evens += 1
	return evens%2 == 1

min_sum = 40000
subsequence_counter = 0

subsequence = sequence[0:4]
change_index = 0
if condition(subsequence):
	subsequence_counter += 1
for num in sequence[4:]:
	subsequence[change_index] = num
	change_index = (change_index+1)%4
	if condition(subsequence):
		subsequence_counter += 1
		subsequence_sum = sum(subsequence)
		if min_sum > subsequence_sum:
			min_sum = subsequence_sum

print(subsequence_counter , " ", min_sum)


