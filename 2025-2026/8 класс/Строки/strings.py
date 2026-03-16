line = input()

#Посчитаем количество букв в строке
counter = 0

for sym in line:
	if 'a' < sym and sym < 'z':
		counter += 1

print(counter)

'''
#Аналог предудущей программы с использованием номеров символов в строке
counter = 0
for i in range(len(line)): #len(line) - длинна строки
	if 'a' < line[i] and line[i] < 'z':
		counter = counter + 1
		
print(counter)
'''

#Выведем все отдельные слова из введённой фразы
for word in line.split():
	print(word)
	#Если слово содержит hello, поздороваемся с пользователем
	if 'hello' in word.lower():
		print('Hello user!')
