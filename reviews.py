import copy
import statistics
import itertools
from collections import Counter


# This script is used to algorithmically segment a larger group of people into small groups for peer reviews
# We had a team of ~14 people across three different functions (data analyst, engineer and visualization developer)
# Periodically we would get together for peer reviews, and this script was used to split us into smaller groups
#  in such a way that would optimize the following conditions:

# 	One, each teammate's reviewers should be of the same function approximately two-thirds of the time
# 		Feedback from your same function is often most immediately relevant, but exposure to the feedback/work of other functions helps us learn and grow
#		We keep track of the history of previous peer reviews in order to make this work out appropriately over time
#	Two, each teammate's reviewers should be of the same squad approximately two-thirds of the time
#		Same-squad reviews are helpful for cross-training.  they may also have enough background to provide immediately relevant feedback
#		Reviews from a different squad's teammates help us learn and grow from each other
#	Three, variation in reviewers is always best.  Penalties should be given for pairing two individuals who were recently paired together
#		"full" penalty if they were just paired together, "half" penalty if they were paired together the session before that

# To achieve the same-function reviewer goal (two thirds of the time), additional roles are suggested to "add" to the peer review grouping.
# In practice this was difficult to achieve because it was difficult to get an accurate headcount with enough notice to invite the right guest reviewers.
# For example, with only 3 engineers (and only 1-2 regularly participating), it was often difficult to get enough of them to
#  provide opportunities for the engineers to review each other  and still meet the other objectives outlined above.



# THINGS I WANT TO DO TO IMPROVE THIS SCRIPT
# - create a "penalty" concept (multiplicative)
# - very small penalty applied for viz and engineers together (since their work doesn't overlap as much as data/viz or data/engineer)
# - remove some of the hardcoding around number of people and number of other squad people, plus squad name
# - improve the readability of the part where the max criteria is calculated
# - update the way i include "dupcount" so that it scales appropriately
# - calculate max stdev of reviewer count within squad
# - determine if the groups can be different sizes (definitely requires significant effort to rework algorithm)
# - keep track of top results over a certain threshold
# - remove deepcopies where unnecessary
# - allow the option to specify a maximum number of "other" roles (e.g. up to one Engineer available)
# - store things like the history of peer review sessions in a separate file



# full list of possible participants (for cutting/pasting)
#  ['Heidi','Vandana','Humfred','Hari','Sergey','Peter','Nitin','Glenn','Vo','Helena','Kunal','Sandeep','Sai','Johnna']

# people who will participate in this round of peer reviews
thisRoundFS = ['Heidi','Vandana','Humfred','Peter','Nitin','Glenn','Vo','Johnna']

# for keeping track of the best key criteria
bestSolutions = []
bestSumStdev = 1
bestSession = []
bestCriteriaValues = []
extraRolesNeeded = []

# scalars used for weighting the various criteria
weightRoleStdev = 0.9
weightSquadStdev = 1
weightDups = 0.5
weightRoleAve = 2
weightRevDist = 0.15

# include any score below this threshold in the list of "top scores"
#   there must be a better way to do this - I'm just trying to show the top "few" segmentations of the group
topScoreThreshold = 0.64

# how many people should be in each group?
groupSize = 4

# how many groups should there be?
groupCount = 2

# what is the minimum number of people there should be with one role before including a "guest" reviewer?
minSameRole = 2

# specify if there are any guest roles (for members to include from other squads) with maximum numbers
# e.g. it's difficult to include more than one "guest" engineer
roleMaximums = {'Viz':None,'Data':None,'Engineer':1}


# define all the participants, their roles and their squads

everyone = {
	# placeholder roles for testing the effects of including someone from another squad
	'Viz': {'Role':'Viz', 'Squad': 'none'},
	'Data': {'Role':'Data', 'Squad': 'none'},
	'Engineer': {'Role':'Engineer', 'Squad': 'none'},

	# squad Fresh Sprints
	'Heidi': {'Role': 'Viz', 'Squad': 'FS'},
	'Peter': {'Role': 'Data', 'Squad': 'FS'},
	'Sergey': {'Role': 'Data', 'Squad': 'FS'},
	'Sandeep': {'Role': 'Engineer', 'Squad': 'FS'},
	'Rakesh': {'Role': 'Engineer', 'Squad': 'FS'},

	# former team mates (no squad)
	'Navya': {'Role': 'Data', 'Squad': 'formerFS'},
	'Al': {'Role': 'Data', 'Squad': 'formerFS'},
	'Neeharika': {'Role': 'Data', 'Squad': 'formerFS'},
	'Matt': {'Role': 'Viz', 'Squad': 'formerFS'},

	# other squads
	'Nitin': {'Role': 'Data', 'Squad': 'Sam'},
	'Vandana': {'Role': 'Viz', 'Squad': 'Sole'},
	'Kunal': {'Role': 'Data', 'Squad': 'Sam'},
	'Hari': {'Role': 'Viz', 'Squad': 'Sam'},
	'Humfred': {'Role': 'Viz', 'Squad': 'Sam'},
	'Sai': {'Role': 'Engineer', 'Squad': 'Sole'},
	'Glenn': {'Role': 'Data', 'Squad': 'Sole'},
	'Vo': {'Role': 'Data', 'Squad': 'Sole'},
	'Helena': {'Role': 'Data', 'Squad': 'Sam'},
	'Johnna': {'Role': 'Engineer', 'Squad': 'Sam'},
	'Manasa': {'Role': 'Engineer', 'Squad': 'Sam'} # no idea what squad
#	'': {'Role': '', 'Squad': ''}
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
	everyone[person]['ReviewedBySameRole'] = 0
	everyone[person]['ReviewedByOtherRole'] = 0
	everyone[person]['ReviewedSameRole'] = 0
	everyone[person]['ReviewedOtherRole'] = 0
	everyone[person]['ReviewedBySameSquad'] = 0
	everyone[person]['ReviewedByOtherSquad'] = 0
	everyone[person]['ReviewedSameSquad'] = 0
	everyone[person]['ReviewedOtherSquad'] = 0
	everyone[person]['PeopleReviewedCounts'] = {'Heidi':0,'Matt':0,'Humfred':0}  # I can't remember why I hardcoded this part
	everyone[person]['PeopleReviewedThisTime'] = []
	everyone[person]['PeopleReviewedLastTime'] = []
	everyone[person]['PeopleReviewedLastLastTime'] = []

def generate_groups(lst, n):
	if not lst:
		yield []
	else:
		for group in (((lst[0],) + xs) for xs in itertools.combinations(lst[1:], n-1)):
			for groups in generate_groups([x for x in lst if x not in group], n):
				yield [group] + groups

def formatSession(unformattedSession):
	sessionFormatted = []
	for subsession in unformattedSession:
		sessionFormatted.append({})
		for name in subsession:
			sessionFormatted[-1][name] = 'y'
	return sessionFormatted

def countDups(everyoneList):
	dupCount = 0
	# count duplicates between "this time" and "last time"
	# count duplicates between "this time" and "last last time" (half count for each)
	for person in everyoneList:
		dupCount += len(set(everyoneList[person]['PeopleReviewedLastTime']) & set(everyoneList[person]['PeopleReviewedThisTime']))
		dupCount += 0.5 * len(set(everyoneList[person]['PeopleReviewedLastLastTime']) & set(everyoneList[person]['PeopleReviewedThisTime']))
	return dupCount

def countSameRoles(name,nameList,statsList):
	count = 0
	roleOfInterest = statsList[name]['Role']
	for currentName in nameList:
		if name != currentName and statsList[currentName]['Role'] == roleOfInterest:
			count += 1
	return count

def maxStdevOfReviewerCounts(statsList,squadOfInterest):
	maxStdev = 0
	for person in statsList:
		if statsList[person]['Squad'] != squadOfInterest:
			continue
		reviewCounts = []
		for reviewer in statsList[person]['PeopleReviewedCounts']:
			if statsList[reviewer]['Squad'] == statsList[person]['Squad']:
				reviewCounts.append(statsList[person]['PeopleReviewedCounts'][reviewer])
		if statistics.pstdev(reviewCounts) > maxStdev:
			maxStdev = statistics.pstdev(reviewCounts)
	return maxStdev



if groupSize*groupCount-len(thisRoundFS) < 0:
	print('\n',len(thisRoundFS),'participants listed')
	print(groupCount,'groups of',groupSize,'is insufficient\n')
	exit()
elif groupSize*groupCount-len(thisRoundFS) == 0:
	print('\n',groupCount,'groups of',groupSize,'is just enough to account for the',len(thisRoundFS),'participants specified')
	print('no guest reviewers needed at this time')
else:
	print('\n','to make',groupCount,'groups of',groupSize,'we will need',groupCount*groupSize-len(thisRoundFS),'guest reviewers')



for session in history:

	# about to review the next session and add it to each member's history
	# first let's clear 'PeopleReviewedThisTime' and copy it to 'PeopleReviewedLastTime' so we can compare the two lists for each person
	for member in everyone:
		everyone[member]['PeopleReviewedLastLastTime'] = copy.deepcopy(everyone[member]['PeopleReviewedLastTime'])
		everyone[member]['PeopleReviewedLastTime'] = copy.deepcopy(everyone[member]['PeopleReviewedThisTime'])
		everyone[member]['PeopleReviewedThisTime'] = []


	for subsession in session:
		for presenter in subsession:
			for reviewer in subsession:
				if presenter != reviewer and subsession[presenter] == 'y':
					if everyone[presenter]['Role'] == everyone[reviewer]['Role']:
						everyone[presenter]['ReviewedBySameRole'] += 1
						everyone[reviewer]['ReviewedSameRole'] += 1
					else:
						everyone[presenter]['ReviewedByOtherRole'] += 1
						everyone[reviewer]['ReviewedOtherRole'] += 1
					if everyone[presenter]['Squad'] == everyone[reviewer]['Squad']:
						everyone[presenter]['ReviewedBySameSquad'] += 1
						everyone[reviewer]['ReviewedSameSquad'] += 1
					else:
						everyone[presenter]['ReviewedByOtherSquad'] += 1
						everyone[reviewer]['ReviewedOtherSquad'] += 1
					if presenter in everyone[reviewer]['PeopleReviewedCounts']:
						everyone[reviewer]['PeopleReviewedCounts'][presenter] += 1
					else:
						everyone[reviewer]['PeopleReviewedCounts'][presenter] = 1
					
					everyone[reviewer]['PeopleReviewedThisTime'].append(presenter)



thisRound = []
for peopleFromOtherSquads in itertools.combinations_with_replacement(['Viz','Data','Engineer'],groupSize*groupCount-len(thisRoundFS)):

	# check to make sure the solution isn't suggesting too many of a certain role type
	countOfOtherRoles = Counter(peopleFromOtherSquads)
	unfillableRoles = False
	for possibleRole in countOfOtherRoles:
		if roleMaximums[possibleRole] != None and countOfOtherRoles[possibleRole] > roleMaximums[possibleRole]:
			unfillableRoles = True

	if unfillableRoles:
		continue


	thisRound = thisRoundFS + list(peopleFromOtherSquads)

	possibleNextSessions = list(generate_groups(thisRound, groupSize))

	for nextSession in possibleNextSessions:
		# first let's determine if the groups with external members have appropriate splits of roles
		# if we invite a Viz person to join, there should be at least 2 other Viz folks in the group
		appropriateSplit = True
		for subsession in nextSession:
			for fillInRole in ['Viz','Data','Engineer']:
				if fillInRole in subsession and countSameRoles(fillInRole,subsession,everyone) < minSameRole:
					appropriateSplit = False
					break
		if not appropriateSplit:
			continue


		everyoneCp = copy.deepcopy(everyone)

		# about to review the nextSession and add it to each member's history
		# first let's clear 'PeopleReviewedThisTime' and copy it to 'PeopleReviewedLastTime' so we can compare the two lists for each person
		for member in everyoneCp:
			everyoneCp[member]['PeopleReviewedLastLastTime'] = copy.deepcopy(everyoneCp[member]['PeopleReviewedLastTime'])
			everyoneCp[member]['PeopleReviewedLastTime'] = copy.deepcopy(everyoneCp[member]['PeopleReviewedThisTime'])
			everyoneCp[member]['PeopleReviewedThisTime'] = []

		for subsession in formatSession(nextSession):
			for presenter in subsession:
				for reviewer in subsession:
					if presenter != reviewer and subsession[presenter] == 'y':
						if everyoneCp[presenter]['Role'] == everyoneCp[reviewer]['Role']:
							everyoneCp[presenter]['ReviewedBySameRole'] += 1
							everyoneCp[reviewer]['ReviewedSameRole'] += 1
						else:
							everyoneCp[presenter]['ReviewedByOtherRole'] += 1
							everyoneCp[reviewer]['ReviewedOtherRole'] += 1
						if everyoneCp[presenter]['Squad'] == everyoneCp[reviewer]['Squad']:
							everyoneCp[presenter]['ReviewedBySameSquad'] += 1
							everyoneCp[reviewer]['ReviewedSameSquad'] += 1
						else:
							everyoneCp[presenter]['ReviewedByOtherSquad'] += 1
							everyoneCp[reviewer]['ReviewedOtherSquad'] += 1
						if presenter in everyoneCp[reviewer]['PeopleReviewedCounts']:
							everyoneCp[reviewer]['PeopleReviewedCounts'][presenter] += 1
						else:
							everyoneCp[reviewer]['PeopleReviewedCounts'][presenter] = 1
						
						everyoneCp[reviewer]['PeopleReviewedThisTime'].append(presenter)

		# calculate the stdevs, update the "best" variables if better than before
		ReviewedBySameSquadPercents = []
		ReviewedBySameRolePercents = []
		for member in everyoneCp:
			if everyoneCp[member]['Squad'] == 'FS':
				ReviewedBySameSquadPercents.append(everyoneCp[member]['ReviewedBySameSquad']/(everyoneCp[member]['ReviewedBySameSquad']+everyoneCp[member]['ReviewedByOtherSquad']))
				ReviewedBySameRolePercents.append(everyoneCp[member]['ReviewedBySameRole']/(everyoneCp[member]['ReviewedBySameRole']+everyoneCp[member]['ReviewedByOtherRole']))

		dupNum = countDups(everyoneCp)/21.0  # 21 is a function of how many people are on the squad and how many groups we split into
		roleStdev = statistics.pstdev(ReviewedBySameRolePercents)
		roleMean = statistics.mean(ReviewedBySameRolePercents)
		squadStdev = statistics.pstdev(ReviewedBySameSquadPercents)
		reviewerDist = maxStdevOfReviewerCounts(everyoneCp,'FS')

		totalScore = (weightRoleStdev*roleStdev+weightSquadStdev*squadStdev+weightDups*dupNum+weightRoleAve*(abs(roleMean-0.67))+weightRevDist*reviewerDist)
		scoreBreakout = [round(num, 5) for num in [weightRoleStdev*roleStdev,weightSquadStdev*squadStdev,weightDups*dupNum,weightRoleAve*abs(roleMean-0.67),weightRevDist*reviewerDist]]

		if totalScore < bestSumStdev:
			bestSumStdev = totalScore
			bestSession = nextSession
			bestCriteriaValues = scoreBreakout
			extraRolesNeeded = peopleFromOtherSquads
		if totalScore < topScoreThreshold:
			bestSolutions.append({'totalScore':round(totalScore,5),'scoreBreakout':scoreBreakout,'session':nextSession,'extrasNeeded':peopleFromOtherSquads})




for solution in bestSolutions:
	print('\ntotalScore:',solution['totalScore'],'   scoreBreakout:',solution['scoreBreakout'],'   guests:',solution['extrasNeeded'])
	print('session:',solution['session'])


print('\n\n\nbest solution:\nscore:',round(bestSumStdev,5),'   breakout:',bestCriteriaValues,'   guests:',extraRolesNeeded)
print('session:',bestSession)
#print("\nbestSumStdev",bestSumStdev)
#print("bestCriteriaValues",bestCriteriaValues)
#print("\nbestSession",bestSession)
#print("extraRolesNeeded",extraRolesNeeded,"\n")
