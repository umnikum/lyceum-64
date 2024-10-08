#Здесь разобраны примеры написания функций


#def - ключеваое слово описывающее функцию
# (): - обязательные параметры(хотябы пустые) и окончание описания
def fact(n):
	#Как и у другх конструкций, сожержание выделяется отступом
	#Сохраняем результат работы в новую переменную
	result = 1
	for 1 in range(1, n):
		#Так как умножение идёт с 1 до n-1, используем как множитель i+1
		result *= i+1
	#Возврщение результата работы осществляется через ключевое слово return
	return result

#Теперь в любом месте программы мы можем писать fact(число/переменная) и получать зачение факториала

#Рассмотрим функцию посложнее:
'''
Посчитаем sin(x) через частичные суммы(для интересующихся: ряд Тейлора)
'''
#Сами задаём предельную точность расчёта:
accuracy = 0.0001

#Формула частичной суммы для нечётного члена:
def partial_sum(x, n):
	return (-1)**n * x**(2*n + 1)  / fact(2*n + 1)

#Начинаем основную программу с ввода x:
x = float(input())

#Значение полной суммы
sin_value = 0
#Номер нечётной частичной суммы
n = 0
#Расчитанное значение частичной суммы, чтобы не вычислять его больше 1го раза
p_sum = patial_sum(x, n)
#Цикл while так как мы не знаем количество частичных сумм
while abs(p_sum) > accuracy:
	#Добавляем значение следующей частичной суммы
	sin_value += p_sum
	#Переходим к следующей, увеличивая номер
	n += 1
	#Рассчитываем следующую
	p_sum = partial_sum(x, n)

#Выводим полученное значение
print(sun_value)
