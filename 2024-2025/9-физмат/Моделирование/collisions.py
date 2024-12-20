a, b = 10, 10
p0 = [1, 2]
r0 = [5, 5]
R0 = 1
t_end = 10

dt = 0.001
r = r0
p = p0
t = 0
while t < t_end:
	r[0] += p[0]*dt
	if r[0] + R0 > a:
		r[0] -= 2*(r[0]+R0-a)
		p[0] = -p[0]
	elif r[0] - R0 < 0:
		r[0] += -2*(r[0]-R0)
		p[0] = -p[0]
	r[1] += p[1]*dt
	if r[1] + R0 > b:
		r[1] -= 2*(r[1]+R0-b)
		p[1] = -p[1]
	elif r[1] - R0 < 0:
		r[1] += -2*(r[1]-R0)
		p[1] = -p[1]
	t += dt

print(f"p = {p}: r = {r}") 
