import copy
import statistics
import itertools
from line_profiler import LineProfiler
from collections import Counter
import random
import math


# This script is used to algorithmically segment a larger group of people into small groups for peer reviews
# We had a team of ~14 people across three different functions (data analyst, engineer and visualization developer)
# Periodically we would get together for peer reviews, and this script was used to split us into smaller groups
#  in such a way that would optimize the following conditions:

# 	One, each teammate's reviewers should be of the same function approximately two-thirds of the time
# 		Feedback from your same function is often most immediately relevant, but exposure to the feedback/work of other functions helps us learn and grow
#		We keep track of the history of previous peer reviews in order to make this work out appropriately over time
#	Two, each teammate's reviewers should be of the same squad approximately two-thirds of the time
#		Same-squad reviews are helpful for cross-training.  they may also have enough background to provide immediately relevant feedback
#		Reviews from a different squad's teammates help us learn and grow from each other's varied perspectives
#	Three, variation in reviewers is always best.  The algorithm applies a penalty for pairing two individuals who were recently paired together
#		"full" penalty if they were just paired together, "half" penalty if they were paired together the session before that

# To achieve the same-function reviewer goal (two thirds of the time), additional roles are suggested to "add" to the peer review grouping.
# In practice this was difficult to achieve because it was difficult to get an accurate headcount with enough notice to invite the right guest reviewers.
# For example, with only 3 engineers (and only 1-2 regularly participating), it was often difficult to get enough of them to
#  provide opportunities for the engineers to review each other and still meet the other objectives outlined above.



# THINGS I WANT TO DO TO IMPROVE THIS SCRIPT
# - create a "penalty" concept (multiplicative)
# - very small penalty applied for viz and engineers together (since their work doesn't overlap as much as data/viz or data/engineer)
# - remove some of the hardcoding around number of people and number of other squad people, plus squad name
# - improve the readability of the part where the max criteria is calculated
# - calculate max stdev of reviewer count within squad
# - determine if the groups can be different sizes (definitely requires significant effort to rework algorithm)
# - store things like the history of peer review sessions in a separate file
# - remove squad dependency from standard deviation of reviewer counts
# - only complain about not enough presenters if it's an issue for all possible group breakout sizes


# THE (NEW) CONSTRAINTS
# - must include 2-3 presenters in each group
# - must include no more than one placeholder person


# QUESTIONS TO ASK OF NEW PARTICIPANTS
# full name
# squad name
# role (viz, data analytics mgr, data engineer, other (describe))
# what are you hoping to get out of peer reviews?



# full list of possible participants (for cutting/pasting)
#  ['Heidi','Vandana','Humfred','Hari','Sergey','Peter','Nitin','Glenn','Vo','Helena','Kunal','Sandeep','Sai','Johnna']


# define the number of top solutions to show
topN = 5

# for keeping track of the best key criteria
bestSumStdev = 10
bestSession = []
bestCriteriaValues = []

# scalars used for weighting the various criteria
weightRoleStdev = 0.9
weightSquadStdev = 0.5
weightDups = 2.5
weightRoleAve = 2
weightRevDist = 0.15


# how many people should be in each group?
groupSize = 5

# how many groups should there be?
groupCount = 2

# what is the minimum number of people there should be with one role before including a "guest" reviewer?
minSameRole = 2

# specify if there are any guest roles (for members to include from other squads) with maximum numbers
# e.g. it's difficult to include more than one "guest" engineer
# roleMaximums = {'Viz':None,'Data':None,'Engineer':1}


idealGroupSizes = {    # participantCount: [list of lists where each represents a possible split of group sizes]
	0: [],
	1: [],
	2: [[2]],
	3: [[3]],
	4: [[4]],
	5: [[5]],
	6: [[6]],
	7: [[3,4]],
	8: [[4,4]],
	9: [[3,3,3],[4,5]],
	10: [[3,3,4],[5,5]],
	11: [[3,4,4]],
	12: [[4,4,4]],
	13: [[3,3,3,4],[4,4,5]],
	14: [[3,3,4,4],[4,5,5]],
	15: [[3,4,4,4],[5,5,5]],
	16: [[4,4,4,4]],
	17: [[3,3,3,4,4],[4,4,4,5]],
	18: [[3,3,4,4,4],[4,4,5,5]],
	19: [[3,4,4,4,4],[4,5,5,5]],
	20: [[4,4,4,4,4]],
	21: [[4,4,4,4,5]],
	22: [[3,3,4,4,4,4],[4,4,4,5,5]],
	23: [[3,4,4,4,4,4],[4,4,5,5,5]],
	24: [[4,4,4,4,4,4],[4,5,5,5,5]],
	25: [[4,4,4,4,4,5]],
	26: [[3,3,4,4,4,4,4],[4,4,4,4,5,5]],
	27: [[3,4,4,4,4,4,4],[4,4,4,5,5,5]]
}


# define all the participants, their roles and their squads
everyone = {
	# placeholder roles for testing the effects of including someone from another squad
	'Viz': {'role':'Viz', 'squad': 'none'},
	'Data': {'role':'Data', 'squad': 'none'},
	'Engineer': {'role':'Engineer', 'squad': 'none'},

	# squad Fresh Sprints
	'Peter': {'role': 'Data', 'squad': 'FS'},
	'Sergey': {'role': 'Data', 'squad': 'FS'},
	'Sandeep': {'role': 'Engineer', 'squad': 'FS'},
	'Rakesh': {'role': 'Engineer', 'squad': 'FS'},
	'Vandana': {'role': 'Viz', 'squad': 'FS'},
	'Seema': {'role': 'Viz', 'squad': 'FS'},
	'Teenu': {'role': 'Data', 'squad': 'FS'},
	'Ashirvad': {'role': 'Data', 'squad': 'FS'},
	'Nitin': {'role': 'Data', 'squad': 'FS'},

	# former team mates (no squad)
	'Navya': {'role': 'Data', 'squad': 'formerFS'},
	'Al': {'role': 'Data', 'squad': 'formerFS'},
	'Neeharika': {'role': 'Data', 'squad': 'formerFS'},
	'Matt': {'role': 'Viz', 'squad': 'formerFS'},

	# other squads
	'Heidi': {'role': 'Viz', 'squad': 'Sole'},
	'Chris': {'role': 'Data', 'squad': 'Sole'},
	'Namit': {'role': 'Engineer','squad': 'Sole'},
	'Kunal': {'role': 'Data', 'squad': 'Sam'},
	'Hari': {'role': 'Viz', 'squad': 'Sam'},
	'Humfred': {'role': 'Viz', 'squad': 'Sam'},
	'Sai': {'role': 'Engineer', 'squad': 'Sole'},
	'Glenn': {'role': 'Data', 'squad': 'Sole'},
	'Vo': {'role': 'Data', 'squad': 'Sole'},
	'Helena': {'role': 'Data', 'squad': 'Sam'},
	'Johnna': {'role': 'Engineer', 'squad': 'Sam'},
	'Manasa': {'role': 'Engineer', 'squad': 'Sole'},
	'Brandon': {'role': 'Viz', 'squad': 'DSM'}
#	'': {'role': '', 'squad': ''}
}

# history of prior peer reviews   name: presenterYN
history = [
	[	# Thursday February 27, 2020
		{'Heidi':'y','Matt':'y','Humfred':'y'},
		{'Peter':'y','Navya':'n','Neeharika':'y','Nitin':'y'},
		{'Sergey':'y','Al':'y','Sandeep':'y','Johnna':'y'}
	],
	[	# Thursday March 12, 2020 (cut short for last minute team huddle)
		{'Heidi':'y','Sandeep':'y','Nitin':'y','Neeharika':'y'},
		{'Sergey':'y','Johnna':'y','Navya':'y','Kunal':'n'},
		{'Humfred':'y','Matt':'y','Al':'y','Vandana':'n'}  #bluejeans confirmed
	],
	[
		# Thursday March 26, 2020
		{'Heidi':'y', 'Matt':'y', 'Sergey':'y', 'Hari':'y'},
		{'Sandeep':'y', 'Humfred':'y', 'Sai':'y'},
		{'Neeharika':'y', 'Navya': 'y', 'Al':'y', 'Glenn':'y'}
	],
	[
		# Monday April 13, 2020
		{'Heidi':'y', 'Humfred':'y'},
		{'Sandeep':'y', 'Rakesh':'y', 'Manasa':'y'},
		{'Neeharika':'y', 'Sergey': 'y', 'Al':'y'}
	],
	[
		# Thursday April 30, 2020
		{'Matt':'y', 'Humfred':'y', 'Navya':'y', 'Neeharika':'y'},
		{'Sergey':'y', 'Al':'y', 'Peter':'y', 'Sandeep':'y'}
	],
	[
		# Thursday June 25, 2020
		{'Heidi':'y', 'Vandana':'y', 'Humfred':'y'},
		{'Glenn':'y', 'Nitin':'y', 'Sergey':'y'},
		{'Peter':'y', 'Vo':'y', 'Sandeep':'y', 'Sai':'y'}
	],
	[
		# Thursday July 30, 2020
		{'Vandana':'y', 'Hari':'y', 'Glenn':'y', 'Sai':'y'},
		{'Sergey':'y', 'Kunal':'y', 'Vo':'y', 'Humfred':'y'},
		{'Heidi':'y', 'Peter':'y', 'Nitin':'y'}
	]
]

for person in everyone:
	everyone[person]['reviewedBySameRole'] = 0				# how many times has person been reviewed by a person of the same role?
	everyone[person]['reviewedByOtherRole'] = 0				# how many times has person been reviewed by a person of a different role?
	everyone[person]['reviewedSameRole'] = 0				# how many times has person reviewed someone of the same role?
	everyone[person]['reviewedOtherRole'] = 0				# how many times has person reviewed someone of a different role?
	everyone[person]['reviewedBySameSquad'] = 0				# how many times has person been reviewed by someone from their squad?
	everyone[person]['reviewedByOtherSquad'] = 0			# how many times has person been reviewed by someone from another squad?
	everyone[person]['reviewedSameSquad'] = 0				# how many times has person reviewed someone from their squad?
	everyone[person]['reviewedOtherSquad'] = 0				# how many times has person reviewed someone from anotehr squad?
	everyone[person]['peopleReviewedCounts'] = {'Heidi':0,'Matt':0,'Humfred':0}  # who has person reviewed and how many times for each?
	everyone[person]['peopleReviewedThisTime'] = []			# which folks did person review this time?
	everyone[person]['peopleReviewedLastTime'] = []			# which folks did person review last time?
	everyone[person]['peopleReviewedLastLastTime'] = []		# which folks did person review the time before last?




def presenterCounts(totalPresCount,groupCount):
	extraPres = totalPresCount % groupCount
	minPres = math.floor(totalPresCount/groupCount)
	maxPres = minPres + 1
	counts = []
	for _ in itertools.repeat(None, groupCount - extraPres):
		counts += [minPres]
	for _ in itertools.repeat(None, extraPres):
		counts += [maxPres]
	return counts


def random_permutation(iterable, r=None):
	"Random selection from itertools.permutations(iterable, r)"
	pool = tuple(iterable)
	r = len(pool) if r is None else r
	return tuple(random.sample(pool, r))


# takes an array of tuples of the form [ ({'name':'Heidi','presenter':'y'},{'name':'Glenn','presenter':'y'}) ]
# and returns an array of tuples of the form [ ('Heidi','Glenn') ]
def sessionNamesOnly(sessionObjects):
	cleanerTuples = []
	for objectTuple in sessionObjects:
		result = tuple(map(lambda s: s['name'], objectTuple))
		cleanerTuples.append(result)
	return cleanerTuples

def sessionHistoryFormat(sessionObjects):
	historyEntry = []
	for objectTuple in sessionObjects:
		result = {}
		for person in objectTuple:
			result[person['name']] = person['presenter']
		historyEntry.append(result)
	return historyEntry


randomGroupings = []

presenters = ["Vandana","Heidi","Peter","Helena","Sai","Glenn","Hari","Kunal","Manasa","Johnna"]
reviewers = ["Rakesh","Navya","Nitin","Matt","Sergey","Sandeep","Neeharika","Al","Humfred","Vo"]

groupSizes = idealGroupSizes[len(presenters + reviewers)]

presObjects = []
for name in presenters:
	presObjects.append({'name':name,'presenter':'y'})
otherObjects = []
for name in reviewers:
	otherObjects.append({'name':name,'presenter':'n'})


for _ in itertools.repeat(None, 5000):
	permPres = random_permutation(presObjects,len(presenters))
	permOther = random_permutation(otherObjects,len(reviewers))
	for groupSizeSet in groupSizes:
		#print("groupSizeSet",groupSizeSet)
		neededPresenters = 2*len(groupSizeSet) - len(presenters)
		if neededPresenters > 0:
			peopleTerm = "person" if neededPresenters == 1 else "people"
			#print("Insufficent presenters - need",neededPresenters,"more",peopleTerm,"to present their work.")
			continue
		presCounts = presenterCounts(len(presenters),len(groupSizeSet))
		#print('continuing with',groupSizeSet)
		groupSet = []
		presIndex = 0
		otherIndex = 0
		for groupIndex, groupSize in enumerate(groupSizeSet):
			thisGroup = permPres[presIndex:presIndex+presCounts[groupIndex]] + permOther[otherIndex:otherIndex+(groupSize - presCounts[groupIndex])]
			groupSet += [thisGroup]

			presIndex += presCounts[groupIndex]
			otherIndex += (groupSize - presCounts[groupIndex])

		randomGroupings += [groupSet]

print(len(randomGroupings),"random groupSets created")




# how many pairs of people are paired together this time and were paired together last time as well?
# divide by the total number of participants to normalize
def countDups(everyoneList):
	dupCount = 0
	# count duplicates between "this time" and "last time"
	# count duplicates between "this time" and "last last time" (half count for each)
	for person in everyoneList:
		dupCount += len(set(everyoneList[person]['peopleReviewedLastTime']) & set(everyoneList[person]['peopleReviewedThisTime']))
		dupCount += 0.5 * len(set(everyoneList[person]['peopleReviewedLastLastTime']) & set(everyoneList[person]['peopleReviewedThisTime']))
	return dupCount/len(everyoneList)



def maxStdevOfReviewerCounts(statsList,squadOfInterest):
	maxStdev = 0
	for person in statsList:
		if statsList[person]['squad'] != squadOfInterest:
			continue
		reviewCounts = []
		for reviewer in statsList[person]['peopleReviewedCounts']:
			if statsList[reviewer]['squad'] == statsList[person]['squad']:
				reviewCounts.append(statsList[person]['peopleReviewedCounts'][reviewer])
		if len(reviewCounts) > 0 and statistics.pstdev(reviewCounts) > maxStdev:
			maxStdev = statistics.pstdev(reviewCounts)
	return maxStdev





for session in history:

	# about to review the next session and add it to each member's history
	# first let's clear 'peopleReviewedThisTime' and copy it to 'peopleReviewedLastTime' so we can compare the two lists for each person
	for member in everyone:
		everyone[member]['peopleReviewedLastLastTime'] = copy.copy(everyone[member]['peopleReviewedLastTime'])
		everyone[member]['peopleReviewedLastTime'] = copy.copy(everyone[member]['peopleReviewedThisTime'])
		everyone[member]['peopleReviewedThisTime'] = []

	# calculate the historical values for 'reviewed by same role', 'reviewed by other role',
	#   'reviewed by same squad', 'reviewed by other squad', 'people reviewed counts' and 'people reviewed last time'
	for subsession in session:
		for presenter in subsession:
			for reviewer in subsession:
				if presenter != reviewer and subsession[presenter] == 'y':
					if everyone[presenter]['role'] == everyone[reviewer]['role']:
						everyone[presenter]['reviewedBySameRole'] += 1
						everyone[reviewer]['reviewedSameRole'] += 1
					else:
						everyone[presenter]['reviewedByOtherRole'] += 1
						everyone[reviewer]['reviewedOtherRole'] += 1
					if everyone[presenter]['squad'] == everyone[reviewer]['squad']:
						everyone[presenter]['reviewedBySameSquad'] += 1
						everyone[reviewer]['reviewedSameSquad'] += 1
					else:
						everyone[presenter]['reviewedByOtherSquad'] += 1
						everyone[reviewer]['reviewedOtherSquad'] += 1
					if presenter in everyone[reviewer]['peopleReviewedCounts']:
						everyone[reviewer]['peopleReviewedCounts'][presenter] += 1
					else:
						everyone[reviewer]['peopleReviewedCounts'][presenter] = 1

					everyone[reviewer]['peopleReviewedThisTime'].append(presenter)




possibleSolutions = []

for nextSession in randomGroupings:
	everyoneCp = copy.deepcopy(everyone)

	# about to review the nextSession and add it to each member's history
	# first let's clear 'peopleReviewedThisTime' and copy it to 'peopleReviewedLastTime' so we can compare the two lists for each person
	for member in everyoneCp:
		everyoneCp[member]['peopleReviewedLastLastTime'] = copy.copy(everyoneCp[member]['peopleReviewedLastTime'])
		everyoneCp[member]['peopleReviewedLastTime'] = copy.copy(everyoneCp[member]['peopleReviewedThisTime'])
		everyoneCp[member]['peopleReviewedThisTime'] = []

	for subsession in nextSession:
		for presenterObject in subsession:
			presenter = presenterObject['name']
			for reviewerObject in subsession:
				reviewer = reviewerObject['name']
				if presenter != reviewer and presenterObject['presenter'] == 'y':
					if everyoneCp[presenter]['role'] == everyoneCp[reviewer]['role']:
						everyoneCp[presenter]['reviewedBySameRole'] += 1
						everyoneCp[reviewer]['reviewedSameRole'] += 1
					else:
						everyoneCp[presenter]['reviewedByOtherRole'] += 1
						everyoneCp[reviewer]['reviewedOtherRole'] += 1
					if everyoneCp[presenter]['squad'] == everyoneCp[reviewer]['squad']:
						everyoneCp[presenter]['reviewedBySameSquad'] += 1
						everyoneCp[reviewer]['reviewedSameSquad'] += 1
					else:
						everyoneCp[presenter]['reviewedByOtherSquad'] += 1
						everyoneCp[reviewer]['reviewedOtherSquad'] += 1
					if presenter in everyoneCp[reviewer]['peopleReviewedCounts']:
						everyoneCp[reviewer]['peopleReviewedCounts'][presenter] += 1
					else:
						everyoneCp[reviewer]['peopleReviewedCounts'][presenter] = 1

					everyoneCp[reviewer]['peopleReviewedThisTime'].append(presenter)


	# calculate the standard deviations of pairs of same squad and pairs of same role (across all persons)
	reviewedBySameSquadPercents = []
	reviewedBySameRolePercents = []
	for member in everyoneCp:
		if (everyoneCp[member]['reviewedBySameSquad']+everyoneCp[member]['reviewedByOtherSquad']) > 0:
			reviewedBySameSquadPercents.append(everyoneCp[member]['reviewedBySameSquad']/(everyoneCp[member]['reviewedBySameSquad']+everyoneCp[member]['reviewedByOtherSquad']))
		if (everyoneCp[member]['reviewedBySameRole']+everyoneCp[member]['reviewedByOtherRole']) > 0:
			reviewedBySameRolePercents.append(everyoneCp[member]['reviewedBySameRole']/(everyoneCp[member]['reviewedBySameRole']+everyoneCp[member]['reviewedByOtherRole']))

	dupNum = countDups(everyoneCp)
	roleStdev = statistics.pstdev(reviewedBySameRolePercents)
	roleMean = statistics.mean(reviewedBySameRolePercents)
	squadStdev = statistics.pstdev(reviewedBySameSquadPercents)
	reviewerDist = maxStdevOfReviewerCounts(everyoneCp,'FS')

	totalScore = (weightRoleStdev*roleStdev+weightSquadStdev*squadStdev+weightDups*dupNum+weightRoleAve*(abs(roleMean-0.67))+weightRevDist*reviewerDist)
	scoreBreakout = [round(num, 5) for num in [
		weightRoleStdev*roleStdev,
		weightSquadStdev*squadStdev,
		weightDups*dupNum,
		weightRoleAve*abs(roleMean-0.67),
		weightRevDist*reviewerDist
	]]

	if totalScore < bestSumStdev:
		bestSumStdev = totalScore
		bestSession = nextSession
		bestCriteriaValues = scoreBreakout
	possibleSolutions.append({'session':nextSession, 'totalScore': round(totalScore,5)})






print('\n\n\nbest solution:\nscore:',round(bestSumStdev,5),'   breakout:',bestCriteriaValues)
print('session:')
for group in sessionNamesOnly(bestSession):
	print("    ",group)
print("\n\n")

# print("\ntop",topN,"solutions")
# for solution in sorted(possibleSolutions, key=lambda sol: sol['totalScore'])[:topN]:
# 	print(solution)


input("...")

print("\n",sessionHistoryFormat(bestSession))

# def random_permutation(iterable, r=None):
#     "Random selection from itertools.permutations(iterable, r)"
#     pool = tuple(iterable)
#     r = len(pool) if r is None else r
#     return tuple(random.sample(pool, r))
