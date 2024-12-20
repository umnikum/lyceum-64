from math import sin, cos

g = 9.8
h = -10
v0 = 20
alpha = 1.57
R0 = 1
r = [0, h]
v = [v0*cos(alpha), v0*sin(alpha)]
dt = 0.001
r_mem = [0, h]
t = 0
while not (r_mem[1]-R0 > 0 and r[1]-R0 < 0):
	r_mem[0], r_mem[1] = r[0], r[1]
	v[1] -= g*dt
	r[0] += v[0]*dt
	r[1] += v[1]*dt
	t += dt

print(f"T = {t}: r = {r}")
