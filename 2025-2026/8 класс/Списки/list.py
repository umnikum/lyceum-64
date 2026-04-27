#Списки это структура хранения набора(массива) данных

digits = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

num = int(input())

if num in digits:		#поиск по списку
	print('digit')		#цифра
else:
	print('not digit')	#не цифра

#Вывести все цирфы сразу
print('All digits:', digits)

#Вывести цифры по очереди в цикле
for digit in digits:
	print('In for:', digit)

#Аналогично, но с индексами
for i in range(len(digits)):
	print('In for:', digits[i])

digits.remove(0)		#Убрать элемент
digits.append('A')		#Добавить элемент в конец

#Ещё раз выведем изменённый набор
print(digits)

'''
#Ввод списка через пробелы:
nums = list(map(int, input().split()))
'''
