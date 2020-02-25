import re
a = input("введите трехзначное число: ")
if re.search('^[1-9][0-9]{2}$',a):
	a = int(a)
	b1 = a // 100
	b2 = a % 100 // 10
	b3 = a % 10
	suma = b1+b2+b3
	proizv = b1*b2*b3
	print ('Сумма =',suma,'; Произведение =',proizv)
else:
	print(a,'- это не трехзначное число')