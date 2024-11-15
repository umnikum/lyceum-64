from mylib import my_function

print(my_function())
#print(my_second_function(1)) #Не работает!

import mylib

#print(my_second_function(2)) #Не работает!
print(mylib.my_second_function(3))
