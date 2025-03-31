
#Размеры спрайта по умолчанию
M, N = 3, 4

#Объявление класса спрайт(картинка)
class Sprite:
#Инициализацтя спрайта строкой содержащей все его символы по очереди
	def __init__(self, init_str, height = M, length = N):
		#Указание внутенних переменныхх класса
		self.height = height
		self.length = length
		#Красивый разбор строки в список подстрок
		self.image = [init_str[length*i:length*(i+1)] for i in range(height)]

#Запись нашего спрайта в строку
	def __str__(self):
		result = ""
		for line in self.image:
			result += line + "\n"
		#Не забываем вернуть что построили
		return result

#Объявление класса сцена(поле)
class Scene(Sprite):
#Немного упростим инициализацию, по умолчанию поле пустое
	def __init__(self, height = 24, length = 80):
		self.height = height
		self.length = length
		self.image = [" "*length for i in range(height)]
#Новый метод draw() будет рисовать картинку в указанных координатах
	def draw(self, sprite, y = 0, x = 0):
		sprite_x_from = 0				#Первый рисуемый символ картинки
		sprite_x_to = sprite.length		#Последний рисуемый символ картинки(если есть)
		x_before = x					#Начальный символ строки в которой будет рисоваться картинка
		x_after = x + sprite.length		#Последний символ строки в которой будет рисоваться картинка(если есть)

		sprite_y_from = 0				#Первая рисуемая строка картинки
		sprite_y_to = sprite.height		#Последня рисуемая строка картинки(если есть)
		y_before = y					#Начальная строка поля в которой будет рисоваться картинка
		y_after = y + sprite.height		#Последняя строка поля в котором будет рисоваться картинка(если есть)
		
		#Хитрые условия на удовлетворения всех краевых случаев, не обязательно!
		if x < 0:
			x_before = 0
			if -x < sprite.length:
				x_after = sprite.length + x
				sprite_x_from = sprite.length - x_after
			else:
				x_after = x_before
				sprite_x_to = 0
		if x_after > self.length:
			if x < self.length:
				sprite_x_to = sprite.length - x_after+self.length
			else:
				x_before = self.length
				sprite_x_to = 0
			x_after = self.length
		
		if y < 0:
			y_before = 0
			if -y < sprite.height:
				y_after = sprite.height + y
				sprite_y_from = sprite.height - y_after
			else:
				y_after = y_before
				sprite_y_to = 0
		if y_after > self.height:
			if x < self.height:
				sprite_y_to = sprite.height - y_after+self.height
			else:
				y_before = self.height
				sprite_y_to = 0
			y_after = self.height
		#Конец всех хитых условий, можно расслабиться!
		
		#Меняем известные нам строки в нужных местах, нужными символами
		for i in range(y_before, y_after):
			row = self.image[i]
			#Не забываем что менять нужно не новую строку row а переменную где хранится само изображение
			self.image[i] = row[0:x_before] + sprite.image[sprite_y_from][sprite_x_from:sprite_x_to] + row[x_after:self.length]
			sprite_y_from += 1

line = ""
grass = Sprite(" \\/ \\\\//_||_") #символическая травка
s = Scene()

# exit - завершение работы пограммы
# y x - 2 координаты в которых должна нарисоваться новая картинка
while "exit" not in line:
	line = input()
	parts = line.split()
	if len(parts) > 1:
		y, x = map(int, line.split())
		s.draw(grass, y, x)
		print(s)

