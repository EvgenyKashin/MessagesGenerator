# when generating messages to txt
GENERATING_MESSAGE_COUNT = 1000

# for generating messages
MIN_WORD_IN_MESSAGE = 4

# when generating hokkus to txt
GENERATING_HOKKU_COUNT = 100

# when it's not None, generates all messages to txt with this first word
# for example: START_WORD = 'hello' - all messages will start with 'hello ..'
START_WORD = None

try:
    from private import *
except Exception as ex:
    print('Create private.py!')
    raise(ex)
