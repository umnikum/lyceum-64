from math import sqrt

N = int(input())

'''
2 - Уникальное чётное простое число, все остальные гарантированно нечётные,
таким образом можно начинать проверку с 3 и использовать шаг в 2 числа
'''
primes = [2]
candidate = 3
while candidate < N:
	is_prime = True
	divisor = 3
	'''
	Нет смысла проверять делители больше чем корень из проверяемого числа.
	Если делитель числа больше корня, то результат деления(тоже делитель) меньше корня и мы бы уже его нашли.
	'''
	while divisor <= sqrt(candidate):
		if candidate % divisor == 0:
			is_prime = False
			break
		divisor += 2
	if is_prime:
		primes.append(candidate)
	candidate += 2
	
print(primes)
