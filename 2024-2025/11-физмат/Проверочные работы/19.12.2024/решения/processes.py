class Process:
	def __init__(self, id, work_time, dependancies):
		self.id = id
		self.work_time = work_time
		if dependancies[0] == 0:
			self.dependancies = []
		else:
			self.dependancies = [elem for elem in dependancies]
		self.delay = 0
	def completion_time(self):
		return self.delay + self.work_time
	def is_working(self, time):
		return time >= self.delay and time < self.completion_time()
	def __str__(self):
		return f"#{self.id} uses {self.work_time} sec, depends on{self.dependancies}"

class Processor:
	def __init__(self, processes = {}):
		self.processes = processes
	def __str__(self):
		result = []
		for process in self.processes.values():
			result.append(f"#{process.id} execution - {process.delay} : {process.completion_time()}")
		return '\n'.join(result)
	def is_jammed(self):
		for process in self.processes.values():
			for id in process.dependancies:
				if self.processes[id].completion_time() > process.delay:
					return True
		return False
	def completion_time(self):
		max_time = 0
		for process in self.processes.values():
			c_time = process.completion_time()
			if c_time > max_time:
				max_time = c_time
		return max_time
	def get_setup(self):
		result = {}
		for process in self.processes.values():
			if process.delay != 0:
				result[process.id] = process.delay
		return result
	def set(self, setup = {}):
		for process in self.processes.values():
			if process.id in setup.keys():
				process.delay = setup[process.id]
			else:
				process.delay = 0
	def peak(self):
		max_load = 0
		max_period = [0, 0]
		cur_period = [0, 0]
		working_mem = 0
		c_time = self.completion_time()
		for t in range(c_time+1):
			working = 0
			for process in self.processes.values():
				if process.is_working(t):
					working += 1
			if working_mem != working:
				if working_mem > max_load or (working_mem == max_load and cur_period[1]-cur_period[0] > max_period[1]-max_period[0]):
					max_period[0], max_period[1] = cur_period[0], cur_period[1]
					max_load = working_mem
				cur_period[0], cur_period[1] = t, t
			working_mem = working
			cur_period[1] = t+1
		return max_load, max_period
	def unjamm(self):
		while self.is_jammed():
			for process in self.processes.values():
				for dependancy in process.dependancies:
					c_time = self.processes[dependancy].completion_time()
					if c_time > process.delay:
						process.delay = c_time

processor = Processor()
with open('процессы.txt', 'r') as infile:
	data = [line.split('\t') for line in infile]
	for initline in data:
		id = int(initline[0])
		dependancies = [int(did) for did in initline[2].split(';')]
		processor.processes[id] =  Process(id, int(initline[1]), dependancies)

def is_better(peak_old, peak_new):
	'''
	if peak_new[0] > peak_old[0]:
		return True
	elif peak_new[0] == peak_old[0] and peak_new[1][1]-peak_new[1][0] > peak_old[1][1]-peak_old[1][0]:'''
	if peak_new[1][1]-peak_new[1][0] > peak_old[1][1]-peak_old[1][0]:
		return True
	else:
		return False

processor.unjamm()
setup = processor.get_setup()
ids = [key for key in processor.processes.keys()]
best_peak = processor.peak()
best_setup = processor.get_setup()

max_return = 15

def variate_delay(index):
	process = processor.processes[ids[index]]
	c_time = processor.completion_time()
	initial_setup = processor.get_setup()
	
	global best_peak
	global best_setup
	for delay in range(process.delay, c_time-process.work_time+1):
		process.delay = delay
		processor.unjamm()
		if processor.completion_time() > c_time:
			break
		new_peak = processor.peak()
		new_setup = processor.get_setup()
		if is_better(best_peak, new_peak):
			best_peak = new_peak
			best_setup.clear()
			best_setup.update(new_setup)
		if index < len(ids)-1:
			variate_delay(index+1)
	processor.set(initial_setup)
	global max_return
	if index < max_return:
		max_return = index
		print(ids[max_return])

variate_delay(0)
processor.set(best_setup)
print(str(processor))
print(best_peak)
