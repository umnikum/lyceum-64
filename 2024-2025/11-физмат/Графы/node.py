class Node:
	def __init__(self, name:str = ''):
		 self.parent = None
		 self.name = name
		 self.children = []
	def append(self, child):
		child.parent = self
		self.children.append(child)
	def __iter__(self):
		return iter(self.children)
	def __str__(self):
		str_children = ''
		if len(self.children) > 0:
			str_children += '{'
			for child in self.children:
				str_children += str(child) + ', '
			str_children = str_children[:-2]
			str_children += '}'
		return self.name + str_children


root = Node('root')
root.append(Node('child_1'))
root.append(Node('child_2'))
for child in root:
	child.append(Node('grand_child_1'))
	child.append(Node('grand_child_2'))
print(root)
