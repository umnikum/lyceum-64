#(X & 94 != 0) -> ((X & 21 == 0) -> (X & A != 0)) = !B -> (C -> !D)
#B + (C -> !D)
#B + !C + !D
#!(B + !C + !D) = !BCD = (X & 94 == 0) * (X & 21 != 0) * (X & A == 0)

A = int(input())

def B(X):
	return X & 94 == 0

def C(X):
	return X & 21 == 0

def D(X):
	return X & A == 0

answer = []
X_interval = [0, 0]
gap = True
for X in range(128):
	if not B(X) and C(X) and D(X):
		if gap:
			X_interval[0] = X
			X_interval[1] = X
			gap = False
		else:
			X_interval[1] = X
	else:
		if not gap:
			gap = True
			if X_interval[1] - X_interval[0] > 1:
				answer.append(X_interval)
			else:
				if X_interval[1] - X_interval[0] >= 0:
					answer.append(X_interval[0])
				if X_interval[1] - X_interval[0] > 0:
					answer.append(X_interval[1])
print(answer)
