# load all the alignments in resource format (i.e. zaln) into data folder

import utils.db_utils as db
import utils.file_utils as file
import time
from datetime import timedelta
from pathlib import Path

############################################
# configure these values for your system
############################################

targetBibleType = 'en_ult'
testament = 1
home = str(Path.home())

origLangPathGreek =  f'{home}/translationCore/resources/el-x-koine/bibles/ugnt/v0.16'
origLangPathHebrew = f'{home}/translationCore/resources/hbo/bibles/uhb/v2.1.16'
targetLanguagePath = f'{home}/translationCore/resources/en/bibles/ult/v18'

############################################

original_words_table = db.original_words_table
target_words_table = db.target_words_table
alignment_table = db.alignment_table
original_words_index_table = db.original_words_index_table
dbPath = f'./data/{targetBibleType}_NT_alignments.sqlite'


# items = db.fetchRecords(connection, original_words_index_table, '')
# print (f"{len(items)} items after reading testament")

########################

# move old sqlite
file.moveFile(f"{dbPath}.save", f"{dbPath}.save2", ifExists=True, overWrite=True)
file.moveFile(dbPath, f"{dbPath}.save", ifExists=True, overWrite=True)

connection = db.initAlignmentDB(dbPath)

########################

# get alignments for NT
start = time.time()
db.getAlignmentsForTestament(connection, 1, targetLanguagePath, origLangPathGreek, targetBibleType, nestedFormat=True)
delta = (time.time() - start)
elapsed = str(timedelta(seconds=delta))
print(f'Get NT alignments, Elapsed time: {elapsed}')

########################

items_target = db.fetchRecords(connection, target_words_table, '')
print (f"{len(items_target)} items in target_words_table")

items_orig = db.fetchRecords(connection, original_words_table, '')
print (f"{len(items_orig)} items in original_words_table")

items_orig_idx = db.fetchRecords(connection, original_words_index_table, '')
print (f"{len(items_orig_idx)} items in original_words_index_table")

items_align = db.fetchRecords(connection, alignment_table, '')
print (f"{len(items_align)} items in alignment_table")

# now see with updated db:
# 183353 items in target_words_table
# 130177 items in alignment_table
# 137962 items in original_words_table

# Get NT alignments - deleting sqlite DB first
# on M1 MBP 13" rosetta: Elapsed time: 0:23:52
# on Dell Laptop: Elapsed time: 0:46:33


