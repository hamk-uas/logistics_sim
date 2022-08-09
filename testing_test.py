import random

original = list(range(0, 22))


sublists = [[] for _ in range(4)]
#print(sublists)

print(original)
print(sublists)

for _ in range(len(original) // len(sublists)):
	for s in sublists:
		s.append(original[0])
		original.remove(original[0])

print(original)
print(sublists)

for i in range(len(original)):
	sublists[i].append(original[i])


print(original)
print(sublists)
