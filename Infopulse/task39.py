a = float(input("введите A: "))
b = float(input("введите B: "))
c = float(input("введите C: "))
d = b**2-4*a*c
if d<0:
	print('решения нет, так как дискриминант отрицательный: ',d)
else:
	x1 = (-b-pow(d,0.5))/(2*a)
	x2 = (-b+pow(d,0.5))/(2*a)
	print('x1 =',x1,'; x2 =',x2)