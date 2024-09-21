#Базовый ввод переменной:
a = int(input())

#Условный оператор:
if a>0:
	#Базовый вывод:
	print('a > 0')
#Синтаксис "иначе":
else:
	if a<0:
		print('a < 0')
	else:
		print('a = 0')

#Указание что переменная список, для дальнейшего обращения:
a_list = []

#Синтаксис цикла for:
for num in range(a//2):
	if a%num == 0:
		#Добавление элемента в список:
		a_list.append(num)
		
print(num)

b_list = []
num = 1
#Синтаксис цикла while:
while(num < a//2):
	if a%num == 0:
		b_list.append(num)

print(b_list)
