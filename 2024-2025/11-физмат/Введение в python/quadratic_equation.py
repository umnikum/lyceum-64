#Ввод дробных переменных:
a = float(input()) 
b = float(input())
c = float(input())

#Функция print может включать много подряд идущих значений, выводимых на экран:
print('Solving: ', a, ' x^2 + ', b, ' x +', c, ' = 0')

x = 0
#Оптимальный порядок проверки условий:
if a == 0:
	if b == 0:
		if c == 0:
			x = 'x is REAL'
		else:
			x = 'There are no solutions!'
	else:
		x = -c / b
else:
	det = b*b - 4*a*c
	if det >= 0:
		x = [(-b + det**0.5)/(2 * a), (-b - det**0.5)/(2 * a)]
	else:
		x = 'There are no REAL solutions!'

#Так как python не имеет строгих типов переменных, x может содержать что угодно, но всё равно выводиться:
print(x)
