import os
import random

random.seed()

depth = 50
dir_width = depth//10
origin = os.path.join('root')

def is_origin(dirpath):
	return os.path.samefile(origin, dirpath)

def next_dir(dirpath):
	max_num = 0
	for entry in os.scandir(dirpath):
		if os.path.isdir(entry):
			try:
				num = int(os.path.basename(entry))
				if num > max_num:
					max_num = num
			except:
				print('Found unexpected foulder: ', os.path.normpath(entry))
	return os.path.join(dirpath, str(max_num+1))

def probability(dirpath):
	size = 0
	for dir in os.scandir(os.path.dirname(dirpath)):
		size += 1
	if size - random.randint(0, dir_width) > 0:
		return 1
	else:
		return 0

def create_map():
	if not os.path.exists(origin):
		os.makedirs(origin)
	path = origin
	counter = 0
	treasure_counter = random.randint(depth//2, depth-1)
	while(counter < depth):
		job = 0
		while(job == 0 and not is_origin(path)):
			job = probability(path)
			if job == 0:
				path = os.path.dirname(path)
		path = next_dir(path)
		if not os.path.exists(path):
			os.makedirs(path)
		counter += 1
		if counter == treasure_counter:
			with open(os.path.join(path, 'treasure.txt'), 'w') as outfile:
				outfile.write('Chest conatains: {} coins!'.format(random.randint(10, 1000)))
