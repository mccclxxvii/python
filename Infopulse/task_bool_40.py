import re
x = input("введите координаты первой клетки")
y = input("введите координаты второй клетки")
if re.search('^[1-8][A-Ha-h]$',x) and re.search('^[1-8][A-Ha-h]$',y):
	x1 = int(x[0])
	y1 = int(y[0])
	x2 = ord(x[1].upper()) % ord("A") + 1
	y2 = ord(y[1].upper()) % ord("A") + 1
	if abs(x1-y1)==2 and abs(x2-y2)==1 or abs(x1-y1)==1 and abs(x2-y2)==2:
		print('Истина')
	else:
		print ('Ложь')