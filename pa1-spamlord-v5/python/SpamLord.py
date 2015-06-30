import sys
import os
import re
import pprint

UNICODE_MAP = {
    'lt'    : '<',
    'gt'    : '>',
    'amp'   : '&',
    'nbsp'  : ' ',
    'quot'  : '"',
    'ldquo' : '"',
    'rdquo' : '"',
    'lsquo' : "'",
    'rsquo' : "'",
    'middot': chr(183),
    'hellip': '...',
    'mdash' : '-',
    'ndash' : '-',
}

UNICODE_TAIL = UNICODE_MAP.keys() + ['#x[\da-f]{2,4}', '#\d{2,4}']
UNICODE_FULL = re.compile(r'&(%s);' % '|'.join(UNICODE_TAIL))
UNICODE_CANDIDATES = re.compile(r'&[a-z]{2,6};')

def convertUnicode(line):
    def replacer(m):
        p = m.group(1)
        if p in UNICODE_MAP.keys():
            return UNICODE_MAP[p]
        else:
             n = int(p[2:], 16) if p[1] == 'x' else int(p[1:])
             return chr(n) if n <= 255 else ' '

    line = UNICODE_FULL.sub(replacer, line)
    return line

def preprocessGeneral(line):
    line = line.lower()
    return convertUnicode(line)

OBFUSCATE_HTML = re.compile(r"obfuscate\('(.*)','(.*)'\)")

def getEmailsObfuscate(line):
    return ['%s@%s' % (m[1], m[0]) for m in OBFUSCATE_HTML.findall(line)]

EMAIL_SYMBOLS_FILTER_MAP = {
    '-': '',
    '(': '',
    ')': '',
    '[': '',
    ']': '',
    '"': '',
    'followed by': '',
     ';' : '.'
}

def utilitySymbolToRe(s):
    if s in '()[]{}.+*':
        return r'\%s' % s
    return s

EMAIL_FILTER = re.compile('|'.join([utilitySymbolToRe(s) for s in EMAIL_SYMBOLS_FILTER_MAP.keys()]))
AT_SYMBOL = re.compile(r'\s(?:at|where)\s', re.IGNORECASE)
DOT_SYMBOL = re.compile(r'\s(?:do?t|dom)\s', re.IGNORECASE)
EMAIL = re.compile(r'''
    (\w+(?:\s*(?(1)[\.\s]|\.)\s*\w+)*)  # Name with optional spacing between letters
    \s*                                 # Optional space
    @                                   # Separator
    \s*                                 # Optional space
    (\w+(?:\s*(?(1)[\.\s]|\.)\s*\w+)*)  # Domain prefix with optional spacing between letters
    \s*                                 # Optional space
    \.?                                 # Optional .
    \s*                                 # Optional space
    ((?:edu|com)                        # top level names
    (?:\.[a-z]{2})?)                    # and optional country code
    (?:\b|$)                            # Make sure this is the end
    ''',
    re.VERBOSE)

# Names to exclude in  <name>@<domain> matches
NAME_EXCLUSIONS = ['server',  'name']
DOTS_SPACES = re.compile(r'[\.\s]+')

def getEmails(line):
    def preprocess(line):
        line = EMAIL_FILTER.sub(lambda m: EMAIL_SYMBOLS_FILTER_MAP[m.group(0)], line)
        line = AT_SYMBOL.sub('@', line)
        line = DOT_SYMBOL.sub('.', line)
        return line

    def postprocess(m):
        return tuple([DOTS_SPACES.sub('.', x) for x in m])

    matches = [postprocess(m) for m in EMAIL.findall(preprocess(line))]
    return ['%s@%s.%s' % m for m in matches if m[0] not in NAME_EXCLUSIONS]


PHONE_NUMBER = re.compile('(\d{3})[\s\-\)]{1,3}(\d{3})[\s\-]{1,3}(\d{4})')

def getPhones(line):
    return ['%s-%s-%s' % m for m in PHONE_NUMBER.findall(line)]

def extract_personal_info(name, line):
    line = preprocessGeneral(line)
    return [(name,'e',email) for email in getEmailsObfuscate(line)]  \
         + [(name,'e',email) for email in getEmails(line)]  \
         + [(name,'p',phone) for phone in getPhones(line)]

""" 
TODO
This function takes in a filename along with the file object (actually
a StringIO object at submission time) and
scans its contents against regex patterns. It returns a list of
(filename, type, value) tuples where type is either an 'e' or a 'p'
for e-mail or phone, and value is the formatted phone number or e-mail.
The canonical formats are:
     (name, 'p', '###-###-#####')
     (name, 'e', 'someone@something')
If the numbers you submit are formatted differently they will not
match the gold answers

NOTE: ***don't change this interface***, as it will be called directly by
the submit script

NOTE: You shouldn't need to worry about this, but just so you know, the
'f' parameter below will be of type StringIO at submission time. So, make
sure you check the StringIO interface if you do anything really tricky,
though StringIO should support most everything.
"""
def process_file(name, f):
    # note that debug info should be printed to stderr
    # sys.stderr.write('[process_file]\tprocessing file: %s\n' % (path))
    res = []
    return sum([extract_personal_info(name, line) for line in f], [])

"""
You should not need to edit this function, nor should you alter
its interface as it will be called directly by the submit script
"""
def process_dir(data_path):
    # get candidates
    guess_list = []
    for fname in os.listdir(data_path):
        if fname[0] == '.':
            continue
        path = os.path.join(data_path,fname)
        f = open(path,'r')
        f_guesses = process_file(fname, f)
        guess_list.extend(f_guesses)
    return guess_list

"""
You should not need to edit this function.
Given a path to a tsv file of gold e-mails and phone numbers
this function returns a list of tuples of the canonical form:
(filename, type, value)
"""
def get_gold(gold_path):
    # get gold answers
    gold_list = []
    f_gold = open(gold_path,'r')
    for line in f_gold:
        gold_list.append(tuple(line.strip().split('\t')))
    return gold_list

"""
You should not need to edit this function.
Given a list of guessed contacts and gold contacts, this function
computes the intersection and set differences, to compute the true
positives, false positives and false negatives.  Importantly, it
converts all of the values to lower case before comparing
"""
def score(guess_list, gold_list):
    guess_list = [(fname, _type, value.lower()) for (fname, _type, value) in guess_list]
    gold_list = [(fname, _type, value.lower()) for (fname, _type, value) in gold_list]
    guess_set = set(guess_list)
    gold_set = set(gold_list)

    tp = guess_set.intersection(gold_set)
    fp = guess_set - gold_set
    fn = gold_set - guess_set

    pp = pprint.PrettyPrinter()
    #print 'Guesses (%d): ' % len(guess_set)
    #pp.pprint(guess_set)
    #print 'Gold (%d): ' % len(gold_set)
    #pp.pprint(gold_set)
    print 'True Positives (%d): ' % len(tp)
    pp.pprint(tp)
    print 'False Positives (%d): ' % len(fp)
    pp.pprint(fp)
    print 'False Negatives (%d): ' % len(fn)
    pp.pprint(fn)
    print 'Summary: tp=%d, fp=%d, fn=%d' % (len(tp),len(fp),len(fn))

"""
You should not need to edit this function.
It takes in the string path to the data directory and the
gold file
"""
def main(data_path, gold_path):
    guess_list = process_dir(data_path)
    gold_list =  get_gold(gold_path)
    score(guess_list, gold_list)

"""
commandline interface takes a directory name and gold file.
It then processes each file within that directory and extracts any
matching e-mails or phone numbers and compares them to the gold file
"""
if __name__ == '__main__':
    if (len(sys.argv) != 3):
        print 'usage:\tSpamLord.py <data_dir> <gold_file>'
        sys.exit(0)
    main(sys.argv[1],sys.argv[2])
