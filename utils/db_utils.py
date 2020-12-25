import pandas as pd
import csv
import json
import sqlite3
from sqlite3 import Error
import utils.file_utils as file
import utils.bible_utils as bible

original_words_table = 'original_words'
target_words_table = 'target_words'
alignment_table = 'alignment_table'
original_words_index_table = 'original_words_index_table'
origLangPathGreek = './data/OrigLangJson/ugnt/v0.14'
origLangPathHebrew = './data/OrigLangJson/uhb/v2.1.15'
targetLangPathEn = './data/TargetLangJson/ult/v14'

def create_connection(path):
    connection = None
    try:
        connection = sqlite3.connect(path)
        print("Connection to SQLite DB successful")
    except Error as e:
        print(f"create_connection - The error '{e}' occurred")

    return connection

def execute_query(connection, query):
    cursor = connection.cursor()
    try:
        cursor.execute(query)
        connection.commit()
        # print("Query executed successfully")
    except Error as e:
        print(f"execute_query - The error '{e}' occurred, query: {query}")

def execute_read_query(connection, query):
    cursor = connection.cursor()
    result = None
    try:
        cursor.execute(query)
        result = cursor.fetchall()
        return result
    except Error as e:
        print(f"execute_read_query - The error '{e}' occurred, query: {query}")

def execute_read_query_dict(connection, query):
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    result = None
    try:
        cursor.execute(query)
        found = cursor.fetchall()
        result = []
        for r in found:
            row = dict(r)
            # print(row)
            result.append(row)
        return result
    except Error as e:
        print(f"execute_read_query_dict - The error '{e}' occurred, query: {query}")

create_original_words_table = f"""
CREATE TABLE IF NOT EXISTS {original_words_table} (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  book_id TEXT NOT NULL,
  chapter TEXT NOT NULL,
  verse TEXT NOT NULL,
  word_num INTEGER,
  word TEXT NOT NULL,
  occurrence INTEGER,
  strong TEXT,
  lemma TEXT,
  morph TEXT
);
"""

create_target_words_table = f"""
CREATE TABLE IF NOT EXISTS {target_words_table} (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  book_id TEXT NOT NULL,
  chapter TEXT NOT NULL,
  verse TEXT NOT NULL,
  word_num INTEGER,
  word TEXT NOT NULL,
  occurrence INTEGER
);
"""

create_alignment_table = f"""
CREATE TABLE IF NOT EXISTS {alignment_table} (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  book_id TEXT NOT NULL,
  chapter TEXT NOT NULL,
  verse TEXT NOT NULL,
  alignment_num INTEGER,
  orig_lang_keys TEXT NOT NULL,
  target_lang_keys TEXT NOT NULL,
  orig_lang_words TEXT NOT NULL,
  target_lang_words TEXT NOT NULL
);
"""

create_original_words_index_table = f"""
CREATE TABLE IF NOT EXISTS {original_words_index_table} (
  originalWord TEXT PRIMARY KEY,
  lemma TEXT NOT NULL,
  strong TEXT NOT NULL,
  alignments TEXT NOT NULL,
  frequency TEXT NOT NULL
);
"""

# will create and initialize the database if it does not exist or tables not created
# will return connection
def initAlignmentDB(dbPath):
    connection = create_connection(dbPath)
    execute_query(connection, create_original_words_table)
    execute_query(connection, create_target_words_table)
    execute_query(connection, create_alignment_table)
    execute_query(connection, create_original_words_index_table)
    return connection

def resetTable(connection, table):
    print(f"resetTable - dropping table: {table}")
    command = f"DROP TABLE {table};"
    execute_query(connection, create_alignment_table)

    print(f"resetTable - initializing table: {table}")
    if table == target_words_table:
        execute_query(connection, create_target_words_table)
    elif table == alignment_table:
        execute_query(connection, create_alignment_table)
    elif table == original_words_table:
        execute_query(connection, create_original_words_table)
    else:
        print(f"resetTable - unknown table: {table}")

def getWordsFromVerse(verseObjects):
    words = []
    for i in range(len(verseObjects)):
        vo = verseObjects[i]
        type_ = getKey(vo,'type')
        if (type_ == 'word'):
            # print(f'At {i} Found word: {vo}')
            words.append(vo)
        elif (type_ == 'milestone'):
            children = vo['children']
            # print(f"At {i} Found children: {len(children)}")
            child_words = getWordsFromVerse(children)
            words.extend(child_words)
            # print('finished processing children')
        elif (type_ == ''):
            print(f"getWordsFromVerse - missing type in: {vo}")

    return words

def parseAlignmentFromVerse(verseObject, wordNum = 0):
    topWords = []
    bottomWords = []
    topWord = verseObject.copy()
    del topWord['children']
    topWord['text'] = topWord['content']
    topWords.append(topWord)

    verseObjects = verseObject['children']

    for i in range(len(verseObjects)):
        vo = verseObjects[i]
        type_ = getKey(vo,'type')
        if (type_ == 'word'):
            # print(f'At {i} Found word: {vo}')
            bottomWords.append(vo)
            wordNum += 1
        elif (type_ == 'milestone'):
            child_topWords, child_bottomWords, child_wordNum = parseAlignmentFromVerse(vo, wordNum)
            topWords.extend(child_topWords)
            bottomWords.extend(child_bottomWords)
            wordNum = child_wordNum
            # print('finished processing children')
        elif (type_ == ''):
            print(f"getWordsFromVerse - missing type in: {vo}")

    return topWords, bottomWords, wordNum

def getAlignmentsFromVerse(verseObjects, wordNum = 0):
    alignments = []
    target_words = []
    wordNum = 0
    for i in range(len(verseObjects)):
        vo = verseObjects[i]
        type_ = getKey(vo,'type')
        if (type_ == 'word'):
            # print(f'At {i} Found word: {vo}')
            target_words.append(vo)
            wordNum += 1
        elif (type_ == 'milestone'):
            topWords, bottomWords, child_wordNum = parseAlignmentFromVerse(vo, wordNum)
            alignment = {
                'topWords': topWords,
                'bottomWords': bottomWords
            }
            alignments.append(alignment)
            target_words.extend(bottomWords)
            wordNum = child_wordNum
            # print('finished processing children')
        # elif (type_ == ''):
        #     print(f"getAlignmentsFromVerse - missing type in: {vo}")

    return target_words, alignments

def getVerseWordsFromChapter(chapter_dict, verse, nestedFormat=False):
    vos = chapter_dict[verse]['verseObjects']
    if nestedFormat:
        words, alignments = getAlignmentsFromVerse(vos)
    else:
       words = getWordsFromVerse(vos)
    return words

def getOccurrences(text, words):
    count = 0
    for word in words:
        if (word['word'] == text):
            count += 1
    return count

def getKey(dict, key, default=''):
    if key in dict:
        return dict[key]
    # print(f"getKey({dict}, {key} - key not found")
    return default

def getDbOrigLangWordsForVerse(words, bookId, chapter, verse):
    db_words = []
    for i in range(len(words)):
        word = words[i]
        text = word['text']
        db_word = {
            'book_id': bookId,
            'chapter': chapter,
            'verse': verse,
            'word_num': i,
            'word': text,
            'occurrence': getOccurrences(text, db_words) + 1,
            'strong': getKey(word,'strong'),
            'lemma': getKey(word,'lemma'),
            'morph': getKey(word,'morph')
        }
        # print(f'At {i} new word entry: {db_word}')
        db_words.append(db_word)
    return db_words

def getDbTargetLangWordsForVerse(words, bookId, chapter, verse):
    db_words = []
    for i in range(len(words)):
        word = words[i]
        text = getWordText(word)
        db_word = {
            'book_id': bookId,
            'chapter': chapter,
            'verse': verse,
            'word_num': i,
            'word': text,
            'occurrence': getOccurrences(text, db_words) + 1
        }
        # print(f'At {i} new word entry: {db_word}')
        db_words.append(db_word)
    return db_words

def getWordText(word):
    key = 'text'
    if key in word:
        return word[key]
    key = 'word'
    if key in word:
        return word[key]
    return ''

def writeRowToDB(connection, table, data, update=False):
    header = getHeader(data)
    row = getDataItems(data)
    if update:
        cmd = 'REPLACE' # actually will also do insert if key not in table
    else:
        cmd = 'INSERT'
    sql = f''' {cmd} INTO {table}({header})
              VALUES({row}) '''
    cur = connection.cursor()
    cur.execute(sql)
    connection.commit()
    return cur.lastrowid

def createCommandToAddToDatabase(table, data):
    header = getHeader(data[0])

    dataStr = ''
    length = len(data)
    for i in range(length):
        rowData = data[i]
        line_data = getDataItems(rowData)
        dataStr += '  (' + line_data
        if (i < length - 1):
            dataStr += '),\n'
        else:
            dataStr += ');\n'

    add_words = f"INSERT INTO\n  {table} ({header})\nVALUES\n{dataStr}"
    return add_words


def getDataItems(db_word):
    line_data = ''
    for key, value in db_word.items():
        if (len(line_data) > 0):
            line_data += ', '

        if isinstance(value, str):
            line_data = f"{line_data}'{value}'"
        else:
            line_data = f"{line_data}{value}"
    return line_data


def getHeader(data):
    header = ''
    for key, value in data.items():
        if (len(header) > 0):
            header += ', '
        header += key
    return header


def addMultipleItemsToDatabase(connection, table, db_words):
    if len(db_words):
        add_words = createCommandToAddToDatabase(table, db_words)
        # print(f"addMultipleItemsToDatabase:\n{add_words}")
        execute_query(connection, add_words)

def fetchRecords(connection, table, filter, caseInsensitive = False, maxRows = None):
    select_items = f"SELECT * FROM {table}"
    if len(filter):
        select_items += f"\nWHERE {filter}"
    if caseInsensitive:
        select_items += ' COLLATE NOCASE'
    if not maxRows is None:
        select_items += f'\n LIMIT {maxRows}'
    # print(f"getRecords:\n{select_items}")
    items = execute_read_query_dict(connection, select_items)
    return items

def fetchWordsForVerse(connection, table, bookId, chapter, verse, maxRows = None):
    filter = f"(book_id = '{bookId}') AND (chapter = '{chapter}') AND (verse = '{verse}')"
    items = fetchRecords(connection, table, filter, maxRows)
    # print(f"getRecords:\n{len(items)}")
    return items

def fetchForWordInVerse(connection, table, word, occurrence, bookId, chapter, verse, maxRows = None):
    filter = f"(book_id = '{bookId}') AND (chapter = '{chapter}') AND (verse = '{verse}') AND (word = '{word}') AND (occurrence = '{occurrence}')"
    items = fetchRecords(connection, table, filter, maxRows)
    # print(f"getRecords:\n{len(items)}")
    return items

def deleteWordsForBook(connection, table, bookId):
    selection = f"book_id = '{bookId}'"
    deleteBook = f"DELETE FROM {table}\nWHERE {selection};\n"
    # print(f"deleteWordsForBook:\n{deleteBook}")
    execute_query(connection, deleteBook)

def getVerses(chapter_dict):
    verses = []
    foundNonNumericalVerse = []
    for verse, verseData in chapter_dict.items():
        try:
            verseNum = int(verse) # make sure its a number
            verses.append(verse)
        except:
            foundNonNumericalVerse.append(verse)
    return verses

def loadAllWordsFromBookIntoDB(connection, origLangPath, bookId, table):
    deleteWordsForBook(connection, table, bookId)

    if table == original_words_table:
        getWordsForVerse = getDbOrigLangWordsForVerse
    else:
        getWordsForVerse = getDbTargetLangWordsForVerse

    chapters = bible.getChaptersForBook(bookId)
    for chapter in chapters:
        print(f"{bookId} - Reading chapter {chapter}")

        chapterPath = f"{origLangPath}/{bookId}/{chapter}.json"
        chapter_dict = file.readJsonFile(chapterPath)
        verses = getVerses(chapter_dict)

        for verse in verses:
            # print(f"Reading verse {verse}")
            words = getVerseWordsFromChapter(chapter_dict, verse)
            db_words = getWordsForVerse(words, bookId, chapter, verse)

            # print(f"For {chapter}:{verse} Saving {len(db_words)}")
            addMultipleItemsToDatabase(connection, table, db_words)

def loadAllWordsFromTestamentIntoDB(connection, origLangPath, newTestament, table):
    books = bible.getBookList(newTestament)
    for book in books:
        print (f"loadAllWordsFromTestamentIntoDB - reading {book}")
        loadAllWordsFromBookIntoDB(connection, origLangPath, book, table)

def findWordsForAlignment(connection, bookId, chapter, verse, alignment, alignmentNum):
    topwords = alignment['topWords']
    bottomWords = alignment['bottomWords']
    origLangWords = topwords
    targetLangWords = bottomWords

    targetIndices = ''
    targetWords = []
    missingWord = False
    for wordTL in targetLangWords:
        word = getWordText(wordTL)
        occurrence = wordTL['occurrence']
        items = fetchForWordInVerse(connection, target_words_table, word, occurrence, bookId, chapter, verse)
        if len(items) > 0:
            if len(targetIndices) > 0:
                targetIndices += ','
            targetWord = items[0]
            pos = str(targetWord['id'])
            targetWords.append(targetWord)
        else:
            pos = '-1'
            missingWord = True
            print(f"saveTargetWordsForAlignment - missing {word}-{occurrence} in {bookId}-{chapter}:{verse}")
        targetIndices += pos
    targetIndices = f",{targetIndices}," # wrap to make searching easier

    originalIndices = ''
    originalWords = []
    for wordOL in origLangWords:
        word = getWordText(wordOL)
        occurrence = wordOL['occurrence']
        items = fetchForWordInVerse(connection, original_words_table, word, occurrence, bookId, chapter, verse)
        if len(items) > 0:
            if len(originalIndices) > 0:
                originalIndices = originalIndices + ','
            originalWord = items[0]
            pos = str(originalWord['id'])
            originalWords.append(originalWord)
        else:
            pos = '-1'
            missingWord = True
            print(f"saveTargetWordsForAlignment - missing {word}-{occurrence} in {bookId}-{chapter}:{verse}")
        originalIndices = originalIndices + pos
    originalIndices = f",{originalIndices}," # wrap to make searching easier

    if missingWord:
        print(f"saveTargetWordsForAlignment - ignoring broken alignment in {bookId}-{chapter}:{verse}")
        return None

    alignment_ = {
        'book_id': bookId,
        'chapter': chapter,
        'verse': verse,
        'alignment_num':alignmentNum,
        'orig_lang_keys':originalIndices,
        'target_lang_keys': targetIndices,
        'orig_lang_words': json.dumps(originalWords, ensure_ascii = False),
        'target_lang_words': json.dumps(targetWords, ensure_ascii = False)
    }
    return alignment_, originalWords, targetWords

def saveAlignmentsForVerse(connection, alignmentsIndex, bookId, chapter, verse, verseAlignments):
    alignmentsFound = False
    numAlignments = len(verseAlignments)
    for i in range(numAlignments):
        verseAlignment = verseAlignments[i]
        alignment, originalWords, targetWords = findWordsForAlignment(connection, bookId, chapter, verse, verseAlignment, i)
        if alignment:
            alignmentsFound = True
            id = writeRowToDB(connection, alignment_table, alignment)
            for origW in originalWords:
                wordText = origW['word']
                if wordText in alignmentsIndex:
                    alignmentList = alignmentsIndex[wordText]['alignments']
                    if id not in alignmentList:
                        alignmentList.append(id)
                else:
                    alignmentsIndex[wordText] = {
                        'originalWord': wordText,
                        'lemma': origW['lemma'],
                        'strong': origW['strong'],
                        'alignments': [ id ],
                        'frequency': ''
                    }
            # addMultipleItemsToDatabase(connection, alignment_table, alignments)
    if not alignmentsFound:
        print(f"saveAlignmentsForVerse - no alignments found in {bookId} {chapter}:{verse}")

def saveAlignmentsForChapter(connection, alignmentsIndex, bookId, chapter, dataFolder, bibleType='', nestedFormat=False):
    if nestedFormat:
        data = bible.loadChapterAlignmentsFromResource(dataFolder, bookId, chapter)
    else:
        data = bible.loadChapterAlignments(dataFolder, bibleType, bookId, chapter)
    verses = getVerses(data)

    for verseAl in verses:
        if nestedFormat:
            target_words, verseAlignments = getAlignmentsFromVerse(data[verseAl]['verseObjects'])
            # save the target words
            db_words = getDbTargetLangWordsForVerse(target_words, bookId, chapter, verseAl)
            addMultipleItemsToDatabase(connection, target_words_table, db_words)
        else:
            verseAlignments = data[verseAl]['alignments']
        # print(f"reading alignments for {bookId} {chapter}:{verseAl}")
        saveAlignmentsForVerse(connection, alignmentsIndex, bookId, chapter, verseAl, verseAlignments)

def saveAlignmentsForBook(connection, alignmentsIndex, bookId, aligmentsFolder, bibleType, origLangPath, nestedFormat=False):
    deleteWordsForBook(connection, alignment_table, bookId)
    deleteWordsForBook(connection, target_words_table, bookId)
    deleteWordsForBook(connection, original_words_table, bookId)

    if nestedFormat:
        bookFolder = aligmentsFolder + '/' + bookId
    else:
        bookFolder = aligmentsFolder + '/' + file.getRepoName(bibleType, bookId)
    files = file.listFolder(bookFolder)
    if files: # make sure folder has files
        print("reading original language words")
        loadAllWordsFromBookIntoDB(connection, origLangPath, bookId, original_words_table)
        if not nestedFormat:
            print("reading target language words")
            loadAllWordsFromBookIntoDB(connection, targetLangPathEn, bookId, target_words_table)

        chapters = bible.getChaptersForBook(bookId)
        for chapterAL in chapters:
            print(f"reading alignments for {bookId} - {chapterAL}")
            saveAlignmentsForChapter(connection, alignmentsIndex, bookId, chapterAL, aligmentsFolder, bibleType, nestedFormat)

    else:
        print(f"No alignments for {bookId} at {bookFolder}")

def getAlignmentsForTestament(connection, newTestament, dataFolder, origLangPath, bibleType, nestedFormat=False):
    books = bible.getBookList(newTestament)
    alignmentsIndex = {}
    for book in books:
        print (f"reading {book}")
        saveAlignmentsForBook(connection, alignmentsIndex, book, dataFolder, bibleType, origLangPath, nestedFormat)

    for word in alignmentsIndex:
        row = alignmentsIndex[word]
        row['alignments'] = json.dumps(row['alignments'])
        id = writeRowToDB(connection, original_words_index_table, row, update=True)

def findAlignmentsFromIndexDbForOrigWord(connection, word, searchLemma, maxRows=None):
    if searchLemma:
        filter = f"(lemma = '{word}')"
    else:
        filter = f"(originalWord = '{word}')"

    # print(f"findAlignmentForWord - filter = {filter}")
    alignments = []
    alignmentsIndex = fetchRecords(connection, original_words_index_table, filter, maxRows)
    if alignmentsIndex and len(alignmentsIndex):
        for index in alignmentsIndex:
            alignmentIds = json.loads(index['alignments'])
            for id in alignmentIds:
                filter = f"(id = '{id}')"
                found = fetchRecords(connection, alignment_table, filter, maxRows=1)
                if len(found):
                    alignments.append(found[0])
    return alignments

def findAlignmentForWord(connection, word, searchOriginal):
    match = str(word['id'])
    matchStr = f"%,{match},%"
    return findAlignmentFor(connection, matchStr, searchOriginal)

def findAlignmentFor(connection, matchStr, searchOriginal):
    if searchOriginal:
        field = 'orig_lang_keys'
    else:
        field = 'target_lang_keys'

    return findAlignmentForField(connection, field, matchStr)

def findAlignmentForField(connection, field, matchStr):
    alignments = findAlignmentsForField(connection, field, matchStr)
    if len(alignments) > 0:
        # print(f"found match: {alignments[0]}")
        return alignments[0]
    else:
        # print(f"match not found for: {matchStr}")
        return None

def findAlignmentsForField(connection, field, matchStr):
    search = f"{field} LIKE '{matchStr}'"
    # print(f"search: {search}")
    alignments = fetchRecords(connection, alignment_table, search)
    return alignments

def findAlignmentsForOriginalWord(connection, word, searchLemma = False):
    field = 'orig_lang_words'

    if searchLemma:
        key = 'lemma'
    else:
        key = 'word'

    matchStr = f'%"{key}": "{word}"%'
    # print(f"matchStr = {matchStr}")
    found = findAlignmentsForField(connection, field, matchStr)
    return found

def lookupWords(connection, alignment, getOriginalWords):
    if getOriginalWords:
        alignedWords = alignment['orig_lang_keys']
        table = original_words_table
    else:
        alignedWords = alignment['target_lang_keys']
        table = target_words_table
    words = []
    # print(f"found ID = {foundId}")
    ids = alignedWords.split(",")
    for id in ids:
        if id:
            found = findWordById(connection, id, table)
            if found:
                words.append(found)
    return words

def combineWordList(words):
    words_ = []
    for word in words:
        words_.append(word['word'])
    return ' '.join(words_)

def getSpan(origWords):
    span = 0
    if len(origWords) > 1:
        wordNums = []
        for word in origWords:
            wordNum = int(word['word_num'])
            wordNums.append(wordNum)
        span = max(wordNums) - min(wordNums)
    return span

def getAlignmentForWord(connection, origWord, searchOriginal):
    alignment = findAlignmentForWord(connection, origWord, searchOriginal)

    if alignment:
        # get original language words
        origWords = lookupWords(connection, alignment, 1)
        alignment['origSpan'] = getSpan(origWords)
        alignment['origWords'] = origWords
        origWordsTxt = combineWordList(origWords)
        alignment['origWordsTxt'] = origWordsTxt
        alignment['alignmentOrigWords'] = len(origWords)

        # get target language words
        targetWords = lookupWords(connection, alignment, 0)
        alignment['targetSpan'] = getSpan(targetWords)
        alignment['targetWords'] = targetWords
        targetWordsTxt = combineWordList(targetWords)
        alignment['targetWordsTxt'] = targetWordsTxt
        alignment['alignmentTargetWords'] = len(targetWords)

        alignment['alignmentTxt'] = f"{origWordsTxt} = {targetWordsTxt}"

    return alignment

def getAlignmentsForWord(connection, origWord, searchOriginal):
    alignments = findAlignmentsForWord(connection, origWord, searchOriginal)

    for alignment in alignments:
        # get original language words
        origWords = lookupWords(connection, alignment, 1)
        alignment['origSpan'] = getSpan(origWords)
        alignment['origWords'] = origWords
        origWordsTxt = combineWordList(origWords)
        alignment['origWordsTxt'] = origWordsTxt
        alignment['alignmentOrigWords'] = len(origWords)

        # get target language words
        targetWords = lookupWords(connection, alignment, 0)
        alignment['targetSpan'] = getSpan(targetWords)
        alignment['targetWords'] = targetWords
        targetWordsTxt = combineWordList(targetWords)
        alignment['targetWordsTxt'] = targetWordsTxt
        alignment['alignmentTargetWords'] = len(targetWords)

        alignment['alignmentTxt'] = f"{origWordsTxt} = {targetWordsTxt}"

    return alignments

def findWordById(connection, id, table):
    search = f"id = {str(id)}"
    items = fetchRecords(connection, table, search)
    if items:
        return items[0]
    print(f"findWordById - {id} not found")
    return None

def findWord(connection, word, searchOriginal = True, searchLemma = False, caseInsensitive = False, maxRows = None):
    if searchLemma:
        search = f"lemma = '{word}'"
    else:
        search = f"word = '{word}'"

    if searchOriginal:
        table = original_words_table
    else:
        table = target_words_table

    words = fetchRecords(connection, table, search, caseInsensitive, maxRows)
    # print (f"{len(words)} items in search: {search}")
    return words

def findWords(connection, words, searchOriginal = True, searchLemma = False, caseInsensitive = False, maxRows = None):
    searches = ''
    for word in words:
        if searchLemma:
            search = f"(lemma = '{word}')"
        else:
            search = f"(word = '{word}')"

        if len(searches) > 0:
            searches += ' OR '

        searches += search

    # print(f"findWords - search filter: {searches}")

    if searchOriginal:
        table = original_words_table
    else:
        table = target_words_table

    words = fetchRecords(connection, table, searches, caseInsensitive, maxRows)
    # print (f"{len(words)} items in search: {search}")
    return words

def getAlignmentsForWords(connection, words, searchOriginal):
    alignments = []
    for word in words:
        alignment = getAlignmentForWord(connection, word, searchOriginal)
        if alignment:
            alignments.append(alignment)
    return alignments

def findAlignmentsForWord(connection, word, searchOriginal = True, searchLemma = False, caseInsensitive = False):
    foundWords = findWord(connection, word, searchOriginal, searchLemma, caseInsensitive)
    # print (f"{len(foundWords)} items in search")

    alignments = getAlignmentsForWords(connection, foundWords, searchOriginal)
    totalCount = len(alignments)
    if totalCount == 0:
        return None

    results = addDataToAlignmentsAndClean(alignments)
    df = pd.DataFrame(results)  # load as dataframe so we can to cool stuff
    return df

# modifies alignment
def convertAlignmentEntryToTable(alignment):
    # get original language words
    origWords = json.loads(alignment['orig_lang_words'])
    alignment['origSpan'] = getSpan(origWords)
    alignment['origWords'] = origWords
    origWordsTxt = combineWordList(origWords)
    alignment['origWordsTxt'] = origWordsTxt
    alignment['alignmentOrigWords'] = len(origWords)
    del alignment['orig_lang_words']

    # get target language words
    targetWords = json.loads(alignment['target_lang_words'])
    alignment['targetSpan'] = getSpan(targetWords)
    alignment['targetWords'] = targetWords
    targetWordsTxt = combineWordList(targetWords)
    alignment['targetWordsTxt'] = targetWordsTxt
    alignment['alignmentTargetWords'] = len(targetWords)
    del alignment['target_lang_words']

    alignment['alignmentTxt'] = f"{origWordsTxt} = {targetWordsTxt}"

def getAlignmentsForOriginalWords(connection, wordList, searchLemma = True):
    origWordAlignments = {}
    # print(f"searchLemma = {searchLemma}")

    for word in wordList:
        # print (f"updating '{word}'")
        alignments = findAlignmentsForOriginalWord(connection, word, searchLemma)
        for alignment in alignments:
            convertAlignmentEntryToTable(alignment)

        if searchLemma:
            alignments_ = splitLemmasAndAddData(alignments, word)
        else:
            alignments_ = addDataToAlignmentsAndClean(alignments)

        for alignment in alignments_:
            origWords = alignment['origWords']
            origWord = findOriginalLanguageForLemma(origWords, word)

            if not origWord is None:
                origWordStr = origWord['word']
                if origWordStr in origWordAlignments:
                    origWordAlignments[origWordStr].append(alignment)
                else:
                    origWordAlignments[origWordStr] = [ alignment ]

    return origWordAlignments

def filterAlignments(alignments, minAlignments=-1):
    if type(alignments) == list:
        alignments = { 'alignments': alignments}

    alignmentsList = []
    rejectedAlignmentsList = []
    for key in alignments.keys():
        alignments_ = alignments[key]
        # print(f"Merging '{key}', size {len(alignments_)}")
        if minAlignments < 0:
            alignmentsList.extend(alignments_)
        else:
            for alignment in alignments_:
                alignmentsCount = alignment['matchCount'] / alignment['frequency']
                if alignmentsCount >= minAlignments:
                    alignmentsList.append(alignment)
                else:
                    rejectedAlignmentsList.append(alignment)

    return alignmentsList, rejectedAlignmentsList

# adds frequency data and converts identification fields to str
def addDataToAlignmentsAndClean(alignments):
    totalCount = len(alignments)
    if totalCount:
        countsMap = pd.DataFrame(alignments)['alignmentTxt'].value_counts()  # get counts for each match type
        # insert frequency of alignment into table
        for alignment in alignments:
            alignmentText = alignment['alignmentTxt']
            if (alignmentText in countsMap):
                count = countsMap[alignmentText]
                ratio = count / totalCount
                alignment['frequency'] = ratio
                alignment['matchCount'] = int(count)
            wordCount = alignment['alignmentTargetWords']
            if wordCount > 1:
                words = alignment['targetWordsTxt'].split(' ')
                if 's' in words: # combine apostrophe
                    pos = words.index('s')
                    if pos > 0:
                        firstPart = words[pos-1]
                        secondPart = words[pos]
                        words[pos-1] = firstPart + "'" + secondPart
                        words.remove('s')
                        newText = ' '.join(words)
                        # print(f'Replacing "{alignment["targetWordsTxt"]}" with "{newText}"')
                        alignment['targetWordsTxt'] = newText
                        alignment['alignmentTxt'] = alignment['origWordsTxt'] + " = " + newText
                        alignment['alignmentTargetWords'] -= 1
                        alignment['targetSpan'] -= 1

            for key in ['id', 'alignment_num']:
                alignment[key] = str(alignment[key]) # converts identification fields to str so that we don't mistakenly try to use for analysis
            alignment['origWordsBetween'] = alignment['origSpan'] - (alignment['alignmentOrigWords'] - 1)
            alignment['targetWordsBetween'] = alignment['targetSpan'] - (alignment['alignmentTargetWords'] - 1)
    return alignments

def splitLemmasAndAddData(alignments, lemma):
    alignmentsList = {}

    for alignment in alignments:
        origWords = alignment['origWords']
        word = findOriginalLanguageForLemma(origWords, lemma)

        if not word is None:
            originalWord = word['word']
            if originalWord in alignmentsList:
                alignmentsList[originalWord].append(alignment)
            else:
                alignmentsList[originalWord] = [ alignment ]
        # else:
            # print(f"splitLemmasAndAddData - Lemma '{lemma}' missing in alignment: {alignment}")

    newAlignments = []
    for originalWord in alignmentsList.keys():
        # print(f"splitLemmasAndAddData - found original word '{originalWord}' for lemma")
        alignments = alignmentsList[originalWord]
        newAlignments_ = addDataToAlignmentsAndClean(alignments)
        newAlignments.extend(newAlignments_)

    return newAlignments

def findOriginalLanguageForLemma(origWords, lemma):
    foundLemmaWord = None
    for word in origWords:
        if word['lemma'] == lemma:
            # print(f"found word: {word}")
            foundLemmaWord = word
            break
    return foundLemmaWord

def findOriginalLanguageWord(origWords, word_, checkLemmas=True):
    foundOriginalWord = None
    for word in origWords:
        if (word['word'] == word_):
            foundOriginalWord = word
            break
        if checkLemmas and (word['lemma'] == word_):
            foundOriginalWord = word
            break
    return foundOriginalWord

def findOriginalWordsForLemma(connection, lemma, maxRows = None):
    foundWords = findWord(connection, lemma, searchOriginal = True, searchLemma = True, caseInsensitive = True, maxRows = maxRows )
    fwd = pd.DataFrame(foundWords)
    return fwd

def findOrignalLangAlignmentsWithTarget(connection, word):
    alignments = findAlignmentsForWord(connection, word, searchOriginal = False, searchLemma = False, caseInsensitive = True)
    return alignments

def findSingleAlignmentsWithTargetWord(connection, word):
    alignments = findOrignalLangAlignmentsWithTarget(connection, word)
    if alignments is not None:
        singleAlignments = alignments.query('alignmentOrigWords==1')
        return singleAlignments
    return None

def findLemmasAlignedWithTarget(connection, word):
    lemmas = []
    singleAlignments = findSingleAlignmentsWithTargetWord(connection, word)
    if singleAlignments is not None:
        for alignment in singleAlignments['origWords']:
            lemma = alignment[0]['lemma']
            # print(lemma)
            lemmas.append(lemma)
        return lemmas
    return None

def findUniqueLemmasAlignedWithTargetWords(connection, wordList, threshold = 1):
    words = wordList.split(' ')
    lemmas = []
    for word in words:
        print(f"searching {word}")
        word_lemmas = findLemmasAlignedWithTarget(connection, word)
        if word_lemmas is not None:
            # print(f"lemmas found {word_lemmas}")
            lemmas.extend(word_lemmas)
    # print(lemmas)
    # make sure they reach threshold
    unique = getUnique(threshold, lemmas)
    return unique

def getUnique(threshold, wordList):
    unique = {}
    for words in wordList:
        if words in unique:
            unique[words] = unique[words] + 1
        else:
            unique[words] = 1

    keys = list(unique.keys())
    if len(keys) > 1:
        for key in keys:
            count = unique[key]
            if not (count >= threshold):
                del unique[key]
    return unique

def saveUniqueLemmasAlignedWithTargetWords(connection, keyTermsPath, wordList, threshold = 2):
    data = file.initJsonFile(keyTermsPath)
    unique = findUniqueLemmasAlignedWithTargetWords(connection, wordList, threshold)
    # print(f"for words '{wordList}' found unique aligned lemmas {unique}")

    data[wordList] = unique # add unique words
    file.writeJsonFile(keyTermsPath, data) # update file
    return unique

def findAlignmentsForWords(connection, wordList, searchOriginal = True, searchLemma = True, caseInsensitive = False, splitLemma = None):
    foundWords = findWords(connection, wordList, searchOriginal, searchLemma, caseInsensitive)
    print (f" for '{wordList}' found {len(foundWords)} usages in database")

    alignments = getAlignmentsForWords(connection, foundWords, searchOriginal)
    print (f" found {len(alignments)} alignments in database")

    totalCount = len(alignments)
    if totalCount == 0:
        return None

    if splitLemma: # if we want to split this lemma into individual morphs
        results = splitLemmasAndAddData(alignments, splitLemma)
    else:
        results = addDataToAlignmentsAndClean(alignments)
    return results

def filterForMinLen(sequence, minLen):
    def filterFunc(variable):
        results = len(variable) >= minLen
        return results

    filtered = filter(filterFunc, sequence)
    return filtered

def saveAlignmentDataForWords(connection, key, wordList_, searchOriginal = True, searchLemma = True, caseInsensitive = True, minLen=-1):
    baseFolder = './data/TrainingData'
    file.makeFolder(baseFolder)

    print(f"getting lemmas for {wordList_}")
    lemmas = []
    foundWords = findWords(connection, wordList_, searchOriginal, searchLemma = False)
    for word in foundWords:
        lemma = word['lemma']
        if not lemma in lemmas:
            lemmas.append(lemma)
    lemmas.sort()
    print(f"found lemmas: {lemmas}")

    wordList = list(filterForMinLen(lemmas, minLen))

    # save superset of alignments
    alignments_df = saveAlignmentDataForWordsSub(connection, key, wordList, baseFolder, searchLemma, searchOriginal,
                                                 caseInsensitive)
    alignmentsSet = {
        key: alignments_df
    }

    length = len(wordList)
    if length > 0:
        # get alignments for each individual word
        for word in wordList:
            alignments_df = saveAlignmentDataForWordsSub(connection, word, [word], baseFolder, searchLemma, searchOriginal,
                                                         caseInsensitive, splitLemma = word)
            alignmentsSet[word] = alignments_df

    return alignmentsSet

def saveAlignmentDataForWordsSub(connection, key, wordList, baseFolder, searchLemma, searchOriginal, caseInsensitive, splitLemma = None):
    alignments = findAlignmentsForWords(connection, wordList, searchOriginal, searchLemma, caseInsensitive, splitLemma = splitLemma)
    if (not alignments) or (len(alignments) < 1):
        print(f"could not find alignments for {wordList}, skipping")
        return []

    print(f"for {key} found {len(alignments)} alignments")
    index = {
        'lemmaList': wordList,
        'alignmentsCount': len(alignments)
    }

    indexPath = baseFolder + '/index.json'
    indexData = file.initJsonFile(indexPath)
    indexData[key] = index
    file.writeJsonFile(indexPath, indexData) # update index

    alignmentTrainingDataPath = baseFolder + '/' + key + '.json'
    file.writeJsonFile(alignmentTrainingDataPath, alignments)

    df = pd.DataFrame(alignments)
    csvPath = baseFolder + '/' + key + '.csv'
    df.to_csv(path_or_buf=csvPath, index=False, header=True, quoting=csv.QUOTE_NONNUMERIC)
    return df

def saveAlignmentDataForLemmas(connection, keyTermsPath, minLen=-1):
    data = file.initJsonFile(keyTermsPath)
    print (f"'{keyTermsPath}' has words: {data}")

    keyTermsList = list(data.keys())
    for keyTerm in keyTermsList:
        item = data[keyTerm]
        print (f"updating '{keyTerm}' = '{item}'")
        saveAlignmentDataForWords(connection, keyTerm, item, searchOriginal = True, searchLemma = True, caseInsensitive = True, minLen = minLen)

# reading dataFrame from json:
def loadAlignmentDataFromFile(lemma):
    alignment_data_path = f'data/TrainingData/{lemma}.json'
    try:
        f = open(alignment_data_path)
        dataStr = f.read()
        data = json.loads(dataStr)
        df = pd.DataFrame(data)
    except FileNotFoundError:
        df = None
        print(f"loadAlignmentDataFromFile - failed to load {lemma} since file not found at {alignment_data_path}")
    return df

def loadAlignmentData(lemma):
    alignment_data_path = f'data/TrainingData/{lemma}.json'
    try:
        f = open(alignment_data_path)
        dataStr = f.read()
        data = json.loads(dataStr)
        df = pd.DataFrame(data)
    except FileNotFoundError:
        df = None
        print(f"loadAlignmentDataFromFile - failed to load {lemma} since file not found at {alignment_data_path}")
    return df

def describeAlignments(alignments, ignore = ['frequency'], silent = False):
    results = {}
    descr = alignments.describe()
    results_desc = dict(descr)
    for key in results_desc.keys():
        new_value = dict(results_desc[key])
        results_desc[key] = new_value
    results['desc'] = results_desc

    if not silent:
        print(f"Alignments description:\n{descr}")

    fields = list(descr.columns)
    if not silent:
        print(f"fields = {fields}")

    results_field = {}
    results['fields'] = results_field

    if ignore:
        for item in ignore:
            fields.remove(item)

    for field in fields:
        alignmentOrigWords_frequency = alignments[field].value_counts()
        if not silent:
            print(f"\nFrequency of {field}:\n{alignmentOrigWords_frequency}")
        results_field[field] = list(alignmentOrigWords_frequency)

    return results

def lookupLexicon(lexiconPath, strongs):
    preChar = strongs[0]
    if preChar == 'G':
        num = strongs[1:5]
        index = int(num)
        filePath = f"{lexiconPath}/{index}.json"
        try:
            data = file.readJsonFile(filePath)
            return data
        except:
            print(f"lookupLexicon - could not read {filePath}")
    else:
        # TODO: Hebrew, Aramaic
        print(f"lookupLexicon - not supported {strongs}")
    return None

def findLemmasForQuotes(connection, quotesPath, lemmasPath, lexiconPath = None):
    data = file.readJsonFile(quotesPath)

    origWords = {}

    def findLemma(origWord):
        if origWord in origWords:
            return None, 0 # if we already checked, skip

        words = findWord(connection, origWord, searchOriginal = True, searchLemma = False, caseInsensitive = True )
        word = words[0]
        count = len(words)
        origWords[origWord] = word
        return word, count

    lemmas = {}
    keys = list(data.keys())
    for key in keys:
        for origWord in data[key]:
            word, count = findLemma(origWord)
            if word:
                lemma = word['lemma']
                print(f"for {origWord} found {lemma}")
                if lemma in lemmas:
                    lemmas[lemma]['count'] += count
                else:
                    strong = word['strong']
                    lemmas[lemma] = {
                        'count': count,
                        'strong': strong
                    }
                    lex = lookupLexicon(lexiconPath, strong)
                    if lex:
                        lemmas[lemma]['lexicon'] = lex

    print(f"findLemmasForQuotes - found {len(lemmas.keys())} lemmas")
    file.writeJsonFile(lemmasPath, lemmas)

def getFrequenciesOfFieldInAlignments(alignmentsForWord, field, sortIndex = False):
    frequenciesOfAlignments = {}
    # for each word add line to plot
    for origWord in alignmentsForWord.keys():
        wordAlignments_ = pd.DataFrame(alignmentsForWord[origWord])
        frequency_ = wordAlignments_[field].value_counts()
        if sortIndex:
            frequency_ = frequency_.sort_index()
        frequenciesOfAlignments[origWord] = frequency_

    return frequenciesOfAlignments

def getDataFrameForOriginalWords(connection, words, searchLemma = True, minAlignments = 100):
    alignments_ = getAlignmentsForOriginalWords(connection, words, searchLemma)
    alignmentsList, rejectedAlignmentsList = filterAlignments(alignments_, minAlignments)
    alignments = pd.DataFrame(alignmentsList)
    return alignments

def getFilteredAlignmentsForWord(alignmentsForWord, minAlignments = 100, remove = []):
    filteredAlignmentsForWord = {}
    for origWord in alignmentsForWord.keys():
        # print(f"{origWord}")
        if origWord not in remove:
            alignments = alignmentsForWord[origWord]
            alignmentsCount = len(alignments)
            if alignmentsCount >= minAlignments:
                alignment = alignments[0]
                word = findOriginalLanguageWord(alignment['origWords'], origWord)
                if (word is not None) and (word['lemma'] not in remove):
                    filteredAlignmentsForWord[origWord] = alignments
                else:
                    word_ = "None" if word is None else word['lemma']
                    print(f"getFilteredAlignmentsForWord - rejecting {origWord} lemma in remove list {word_}")
            # else:
            #     print(f"getFilteredAlignmentsForWord - rejecting {origWord} count {alignmentsCount}")
        # else:
        #     print(f"getFilteredAlignmentsForWord - rejecting {origWord} in remove list")

    return filteredAlignmentsForWord

def getFilteredLemmas(termsPath, minAlignments = 100, remove = []):
    data = file.initJsonFile(termsPath)
    lemmasList = list(data.keys())
    print (f"'{termsPath}' has count: {len(lemmasList)}")
    filteredLemmas = {}
    for lemma in lemmasList:
        item = data[lemma]
        if item['count'] >= minAlignments:
            filteredLemmas[lemma] = item

    for item in remove:
        if item in filteredLemmas:
            del filteredLemmas[item]
    print (f"filtered count: {len(filteredLemmas)}")

    return lemmasList

def zeroFillFrequencies(field_frequencies):
    filledFrequencies = {}
    for originalWord in field_frequencies.keys():
        field_frequency = field_frequencies[originalWord]
        X = []
        Y = []

        def appendXY(x,y):
            X.append(x)
            Y.append(y)

        lastX = 0
        for key in field_frequency.keys():
            x = key
            y = field_frequency[key]
            while x > lastX: # do zero fill
                appendXY(lastX, 0)
                lastX += 1
            appendXY(x, y)
            lastX += 1
        appendXY(lastX, 0)
        filledFrequencies[originalWord] = {
            'X': X,
            'Y': Y
        }
    return filledFrequencies

def fetchAlignmentDataForLemmasCached(connection, type_, bibleType, minAlignments, remove):
    alignmentsForWordPath = f'./data/{type_}_{bibleType}_NT_by_orig.json'
    filteredAlignmentsForWordPath = f'./data/{type_}_{bibleType}_NT_by_orig_{minAlignments}.json'
    lemmasPath = f'./data/{type_}_{bibleType}_NT_lemmas.json'

    # first try to use saved data
    alignmentsForWord = file.initJsonFile(alignmentsForWordPath)

    unfLen = len(list(alignmentsForWord.keys()))
    if not unfLen:
        print("Cache empty")
        lemmasList = getFilteredLemmas(lemmasPath, minAlignments, remove)

        # find all alignments for this lemma
        alignmentsForWord = getAlignmentsForOriginalWords(connection, lemmasList, searchLemma = True)

        # save data to speed things up
        file.writeJsonFile(alignmentsForWordPath, alignmentsForWord)

    else:
        print("Using cached Alignments")

    print(f"Unfiltered Alignments: {len(alignmentsForWord)}")

    # filter by number of alignments for word
    filteredAlignmentsForWord = getFilteredAlignmentsForWord(alignmentsForWord, minAlignments, remove)
    file.writeJsonFile(filteredAlignmentsForWordPath, filteredAlignmentsForWord)

    print(f"Filtered Alignments: {len(filteredAlignmentsForWord)}")

    return alignmentsForWord, filteredAlignmentsForWord

def generateWarnings(type_, bibleType, alignmentsForWord, alignmentOrigWordsThreshold,
                     alignmentTargetWordsThreshold, origWordsBetweenThreshold, targetWordsBetweenThreshold):
    alignmentsToCheck = []

    for origWord in alignmentsForWord.keys():
        alignments = alignmentsForWord[origWord]
        for alignment in alignments:
            warnings = []

            alignmentOrigWords = alignment['alignmentOrigWords']
            if alignmentOrigWords >= alignmentOrigWordsThreshold:
                warnings.append(f"{origWord} - Too many original language words in alignment: {alignmentOrigWords}, threshold {alignmentOrigWordsThreshold}")

            alignmentTargetWords = alignment['alignmentTargetWords']
            if alignmentTargetWords >= alignmentTargetWordsThreshold:
                warnings.append(f"{origWord} - Too many target language words in alignment: {alignmentTargetWords}, threshold {alignmentTargetWordsThreshold}")

            origWordsBetween = alignment['origWordsBetween']
            if origWordsBetween >= origWordsBetweenThreshold:
                warnings.append(f"{origWord} - Discontiguous original language alignment, extra words: {origWordsBetween}, threshold {origWordsBetweenThreshold}")

            targetWordsBetween = alignment['targetWordsBetween']
            if targetWordsBetween >= targetWordsBetweenThreshold:
                warnings.append(f"{origWord} - Discontiguous target language alignment, extra words: {targetWordsBetween}, threshold {targetWordsBetweenThreshold}")

            if len(warnings):
                alignment['warnings'] = json.dumps(warnings, ensure_ascii = False)
                alignmentsToCheck.append(alignment)

    basePath = f'./data/{type_}_{bibleType}_NT_warnings'
    jsonPath = basePath + '.json'
    file.writeJsonFile(jsonPath, alignmentsToCheck)

    df = pd.DataFrame(alignmentsToCheck)
    csvPath = basePath + '.csv'
    warningData = df.drop(columns=["id", "origSpan", "targetSpan"]).sort_values(by=["book_id", "chapter", "verse", "alignment_num"])
    warningData.to_csv(path_or_buf=csvPath, index=False, header=True, quoting=csv.QUOTE_NONNUMERIC)
    return warningData
