from math import sqrt

N = int(input())

primes = [2]
candidate = 3
while candidate < N:
	is_prime = True
	'''
	Так как мы находим ВСЕ простые числа вплоть до N, можно использовать их как потенциальные множители,
	таим образом мы сокращаем сложность перебора до логарифмической
	'''
	i_prime = 0
	while primes[i_prime] <= sqrt(candidate):
		if candidate % primes[i_prime] == 0:
			is_prime = False
			break
		i_prime += 1
	if is_prime:
		primes.append(candidate)
	candidate += 2
	
print(primes)
