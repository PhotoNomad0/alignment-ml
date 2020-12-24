# save

import utils.db_utils as db
import utils.file_utils as file
import time
from datetime import timedelta

############################################
# configure these values for your system
############################################

targetLang = 'en'
bibleType = 'en_ult'
dbPath = f'./data/{bibleType}_alignments.sqlite'

connection = db.initAlignmentDB(dbPath)


################################

# read alignment data for all the lemmas

termsPath = './data/kt_en_NT_lemmas.json'
data = file.initJsonFile(termsPath)
print (f"'{termsPath}' has words: {data}")
lemmasList = list(data.keys())

start = time.time()
alignments = db.getAlignmentsForOriginalWords(connection, lemmasList)
delta = (time.time() - start)
elapsed = str(timedelta(seconds=delta))
print(f'read alignments for lemmas, Elapsed time: {elapsed}')


################################

# flatten the lemmas into an alignment list

alignmentsList, rejectedAlignmentsList = db.filterAlignments(alignments)
termsPath = './data/TrainingData/kt_en_NT_alignments_all.json'
print(f"Unfiltered training list size is {len(alignmentsList)}")
file.writeJsonFile(termsPath, alignmentsList)


################################

# flatten the lemmas into a filtered alignment list

minAlignments = 100
alignmentsList, rejectedAlignmentsList = db.filterAlignments(alignments, minAlignments)
termsPath = './data/TrainingData/kt_en_NT_alignments_filtered_100.json'
print(f"filtered {minAlignments} training list size is {len(alignmentsList)}")
print(f"rejected size is {len(rejectedAlignmentsList)}")
file.writeJsonFile(termsPath, alignmentsList)
