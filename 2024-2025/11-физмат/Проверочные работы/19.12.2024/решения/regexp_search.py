import re

pattern = re.compile(r"[а-яА-Я\-]+его[ \.,!?$-]")
failed_pattern = re.compile(r"[еЕ]го")
ego_pattern = re.compile(r"[ ][еЕ]го[ \.,!?$-]")
word_with_ego_pattern = re.compile(r"[а-яА-Я\-]+[еЕ]го[а-яА-Я\-]+")

text = ''
with open('Текст 3ей истории.txt', 'r') as infile:
	for line in infile:
		text += line

matches = []
for match in pattern.finditer(text):
	begin, end = match.span()
	matches.append(text[begin:end-1])

failed_matches = []
egos = 0
for match in failed_pattern.finditer(text):
	begin, end = match.span()
	correct = False
	sample = text[begin-10:end+10]
	for searchmatch in pattern.finditer(sample):
		search_begin, search_end = searchmatch.span()
		correct = True
	if not correct:
		ego = False
		for searchmatch in ego_pattern.finditer(sample):
			search_begin, search_end = searchmatch.span()
			ego = True
		if ego:
			egos += 1
		else:
			for searchmatch in word_with_ego_pattern.finditer(sample):
				search_begin, search_end = searchmatch.span()
				failed_matches.append(sample[search_begin:search_end])
	

print(len(matches))
print(matches)
print("Его: {}, ошибок: {}\nОшибки:".format(egos, len(failed_matches)))
print(failed_matches)
