#Создаём класс вершины дерева
class Node:
	'''
	Инициализируем:
		parent - родительская вершина(исток)
		dist - расстояние до родительской вершины(по умолчанию 0 если вершина корневая)
		children - лист исходящих вершин
	'''
	def __init__(self, dist:int = 0):
		 self.parent = None
		 self.dist = dist
		 self.children = []

	#Определяем итератор чтобы проходиться по дереву циклом for child in tree:
	def __iter__(self):
		return iter(self.children)
	#Определяем длинну вершины равную длинне списка содержащего исходящие вершины
	def __len__(self):
		return len(self.children)

	#Определяем метод добавляющий исходящую вершину
	def append(self, child):
		child.parent = self
		self.children.append(child)
	#Определяем метод убирающий вершину из исходящих
	def remove(self, target):
		self.children.remove(target)

	#Красиво выводим дерево в строку(не обязательно, но удобно для демонстрации)
	def __str__(self):
		str_children = ''
		if self.dist > 0:
			str_children += str(self.dist)
		if len(self.children) > 0:
			str_children += '{'
			for child in self.children:
				str_children += str(child) + ', '
			str_children = str_children[:-2]
			str_children += '}'
		return str_children

	#Определяем метод перевзвешивания дерева с произвольной вершины
	def set_parent_as_child(self):
		#Если есть прародитель, нужно вызвать метод рекурсивно
		if self.parent.parent != None:
			self.parent.set_parent_as_child()
		#Убираем self из исходящих вершин родителя
		self.parent.remove(self)
		#Добавляем родителя в свои исходящие вершины
		self.append(self.parent)
		#Записываем длинну до родителя внутрь самого родителя
		self.parent.dist = self.dist
		#Затираем всю информацию о бывшем родителе
		self.parent = None
		self.dist = 0

#Рекурсивная функция поиска длиннейшего пути из выделенной вершины
def longest_way(node):
	#Если исходящих вершин нет, возвращаем собственную длинну
	if len(node) == 0:
		return node.dist
	way = 0
	#Иначе для каждой исходящей вершины:
	for child in node:
		#Рекурсивно повторяем функцию
		search = longest_way(child)
		#Проверяем если потенциальный путь оказался длинней
		if search > way:
			way = search
	#Добавляем собственную длинну возвращаясь в родительскую вершину
	way += node.dist
	return way
		

root = Node()
root.append(Node(1))
root.append(Node(10))
for child in root:
	child.append(Node(1))
	child.append(Node(2))
print(root)

print(longest_way(root))
node = next(iter(root))
node.set_parent_as_child()
print(node)
print(longest_way(node))
