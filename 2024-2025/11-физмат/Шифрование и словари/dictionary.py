'''
Двоичная запись целого числа начинается с 0b

Чтобы представить число в двоичной системе:
bin(число) - от binary/двоичная
Для записи в двоичный код нужно пропустить 2 первых символа


Чтобы из двоичной строки получить целое число:
int(строка, 2) - где 2 это основание системы
'''

#Шифр создан словарём, для удобности в двоичном виде:
cifer = {'a':0b10001,
		 'b':0b1110}

#Обратный код получен процедурно:
solution = {value: key for key, value in cifer.items()}

#Создаём функцию кодирования:
def code(message):
	#В ошибках хранятся символы отсутствующие в шифре
	errors = []
	result = ''
	for literal in message:
		if literal in cifer:
			result += bin(cifer[literal])[2:]
		else:
			if not literal in errors:
				errors.append(literal)
	#Рассказываем о исключениях, чтобы была возможность их исправить в шифре
	for literal in errors:
		print('Unable to cifer:', literal)
	return result

#Создаём функцию раскодирования:
def decode(message):
	result = ''
	#Так как теперь сообщение имеет несколько битов на символ, необходимо слово:
	word = ''
	for literal in message:
		word += literal
		#Рачитываем потенциальный ключ
		key = int(word,2)
		#Ищем ключ в обратном шифре:
		if key in solution:
			result += solution[key]
			#Не забыаем очистить слово
			word = ''
	#Если слово не раскодировалось, сообщаем об ошибке:
	if len(word) > 0:
		print('Unable to decode, size: ', len(word))
	return result

line = input()
#Если вводили сообщение:
print('Resulting code:\n', code(line))
#Если вводили код:
#print('Decifered message:\n', decode(line))
