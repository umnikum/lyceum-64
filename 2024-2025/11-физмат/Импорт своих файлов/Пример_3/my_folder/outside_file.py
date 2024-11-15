import sys 
import os
sys.path.append(os.path.abspath("../")) #Выйти из паки 1ин раз в нашем случае, абстрактно ваш путь до модуля
from module.mylib import *

print(my_second_function(1))
