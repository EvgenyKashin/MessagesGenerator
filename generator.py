# -*- coding: utf-8 -*-
"""
Created on Mon Jul 11 16:34:30 2016

@author: EvgenyKashin
"""

import requests
import json
import math
import time
from collections import Counter
from collections import defaultdict
import re
import random
import sys
import getopt
import config

msg_url = 'https://api.vk.com/method/messages.getHistory?user_id={}&\
           &access_token={}&v=5.52&count={}&offset={}&rev={}'


def memo(f):
    cache = {}

    def wrapped(*args):
        if args not in cache:
            cache[args] = f(*args)
        return cache[args]
    wrapped.cache = cache
    return wrapped


def memo_list(f):
    cache = {}

    def wrapped(*args):
        if ''.join(args[0]) not in cache:
            cache[''.join(args[0])] = f(*args)
        return cache[''.join(args[0])]
    wrapped.cache = cache
    return wrapped


def get_messages_history(user_id, count=5,
                         offset=0, rev=1):
    # user_id - user whose message history to return
    url = msg_url.format(user_id, config.TOKEN, count, offset, rev)
    r = requests.get(url)
    return json.loads(r.text)


def parse_messages(msgs):
    # All messeges in a row from one user are joined in the one big message
    my, other = [], []
    my_msg, other_msg = '', ''
    is_my = None
    for msg in msgs:
        if True:
            # if message is outgoing
            if msg['out'] == 1:
                if not is_my:
                    if other_msg:
                        other.append(other_msg)
                    is_my = True
                    if 'attachments' not in msg:
                        my_msg = msg['body']
                    else:
                        my_msg = ''
                else:
                    if 'attachments' not in msg:
                        my_msg += '\n' + msg['body']
            else:
                if is_my is None or is_my:  # for first start
                    if my_msg:
                        my.append(my_msg)
                    is_my = False
                    if 'attachments' not in msg:
                        other_msg = msg['body']
                    else:
                        other_msg = ''
                else:
                    if 'attachments' not in msg:
                        other_msg += '\n' + msg['body']
    return my, other


def download_messages(user_id, max_iter=None):
    my_messages = []
    other_messages = []

    # test message to know total count
    messages = get_messages_history(user_id, 1)
    count = int(messages['response']['count'])
    print(count, 'total messages')
    iteration = math.ceil(count / 200)
    if max_iter:
        iteration = min(iteration, max_iter)

    for i in range(iteration):
        if i % 10 == 0:
            print('{:.2f}%'.format(i / iteration * 100))

        messages = get_messages_history(user_id, 200, i * 200)
        my, other = parse_messages(messages['response']['items'])
        my_messages.extend(my)
        other_messages.extend(other)

        # each message separated by \n\n
        my_filename = 'data/to_{}.txt'.format(user_id)
        other_filename = 'data/from_{}.txt'.format(user_id)
        with open(my_filename, 'a', encoding='utf-8') as f:
            f.write('\n\n'.join(my))
            f.write('\n\n')
        with open(other_filename, 'a', encoding='utf-8') as f:
            f.write('\n\n'.join(other))
            f.write('\n\n')

        # because of limit for calling api
        time.sleep(0.33)
    return my_messages, other_messages


def read_messages(user_id):
    my_filename = 'data/to_{}.txt'.format(user_id)
    other_filename = 'data/from_{}.txt'.format(user_id)
    my, other = None, None

    with open(my_filename, 'r', encoding='utf-8') as f:
        my = f.read().split('\n\n')
    with open(other_filename, 'r', encoding='utf-8') as f:
        other = f.read().split('\n\n')
    return my, other


def words_from_message(message):
    # split only by spaces
    # removing commas
    words = re.split(r'[ ]', message)
    words = [re.sub(',', '', word) for word in words]
    return [word.strip().lower() for word in words if word]


def words_from_messages(messages):
    messages = [str.rstrip(msg) for msg in messages]
    words = (' '.join(messages)).split(r' ')
    return list(map(str.strip, words))


def counter_from_messages(messages):
    words = words_from_messages(messages)
    return Counter(words)


def prepare_words(words):
    # processing newline sybmol
    i = 0
    l = len(words)
    while i < l:
        word = words[i]
        if '\n' in word:
            splitted_word = word.split('\n')
            words = words[:i] + [splitted_word[0]] + ['.'] +\
                                [splitted_word[1]] + words[i + 1:]
            l += 2  # were 1 became 3 words
            i += 1  # skiping '.'
        i += 1

    # processing punctuation
    i = 0
    l = len(words)
    while i < l:
        word = words[i]
        for sign in ['?', '!', '.']:
            if sign in word:
                splitted_word = word.split(sign)
                words = words[:i] + [splitted_word[0]] + [sign] + ['.'] +\
                        words[i + 1:]
                l += 2  # were 1 became 3 words
                i += 2  # skiping sign and '.'
                break  # sybmol has already founded
        i += 1
    return [w for w in words if w]


@memo_list
def bigram_from_messages(messages):
    """
    return transition and start_words
    start_words - first word and word before a period symbol. Same word can be
        added multipy times. The greater the number of times the word appears
        the greater the probability of starting a message from this word.
    transitions - list of list, where list - transitions['your_word'] contains
        all word wich can be generated after 'your_word'. Using the same idea
        with probabilities.
    @memo_list for better perfomance
    """

    transitions = defaultdict(list)
    start_words = []
    for msg in messages:
        words = words_from_message(msg)
        words = prepare_words(words)
        if len(words) > 2:
            words = ['.'] + words  # for adding first word into start_words
            bigrams = zip(words, words[1:])
            for prev, current in bigrams:
                if prev == '.' and re.match(r'[а-яa-z]+', current):
                    start_words.append(current)
                transitions[prev].append(current)
    return transitions, start_words


@memo_list
def trigram_from_messages(messages):
    """
    return transition and start_words
    start_words - first word and word before a period symbol. Same word can be
        added multipy times. The greater the number of times the word appears
        the greater the probability of starting a message from this word.
    transitions - list of list, where list -
        transitions[('first_word', 'second_word')] contains
        all word wich can be generated after pair 'wirst_word second_word'.
        Using the same idea with probabilities.
    @memo_list for better perfomance
    """

    transitions = defaultdict(list)
    start_words = []
    for msg in messages:
        words = words_from_message(msg)
        words = prepare_words(words)
        if len(words) > 2:
            start_words.append(words[0])
            trigrams = zip(words, words[1:], words[2:])
            for prev, current, next in trigrams:
                if prev == '.' and re.match(r'[а-яa-z]+', current):
                    start_words.append(current)
                transitions[(prev, current)].append(next)
    return transitions, start_words


def generate_with_bigrams(start_words, transitions, start_word=None):
    current = random.choice(start_words)
    if start_word:
        # check for existing of pairs with start_word
        if len([w for w in filter(lambda x: x != '.',
                                  transitions[start_word])]) == 0:
            raise Exception('Wrong start_word!\
                             No message starting like this: {}'
                            .format(start_word))
        current = start_word
    result = [current]
    while True:
        next_word_candidates = transitions[current]
        # this condition need for avoiding infinire loop
        if len(set(filter(lambda x: x not in ['.', ',', '!', '?', ':'],
                          next_word_candidates))) > 1:
            current = random.choice(next_word_candidates)
        else:
            return ' '.join(result)

        if current == '.':
            return ' '.join(result)
        else:
            result.append(current)


def generate_with_trigrams(start_words, transitions, start_word=None):
    current = random.choice(start_words)
    prev = random.choice(start_words)
    if start_word:
        # check for existing of pairs with start_word
        if len([w for w in filter(lambda x: x != '.',
                                  transitions[start_word])]) == 0:
            raise Exception('Wrong start_word!\
                             No message starting like this: {}'
                            .format(start_word))
        current = start_word
    result = [current]
    while True:
        next_word_candidates = transitions[(prev, current)]
        # this condition need for avoiding infinire loop
        if len(set(filter(lambda x: x not in ['.', ',', '!', '?', ':'],
                          next_word_candidates))) > 1:
            next_word = random.choice(next_word_candidates)
            prev, current = current, next_word
        else:
            return ' '.join(result)

        if current == '.':
            return ' '.join(result)
        else:
            result.append(current)


def generate_messages_bigrams(messages, count=5, start_word=None, min_word=4):
    trans, starts = bigram_from_messages(messages)
    i = 0
    result = []
    while i < count:
        msg = generate_with_bigrams(starts, trans, start_word)
        if len(words_from_message(msg)) > min_word:
            result.append(msg)
            i += 1
            if i % 200 == 0:
                print('{:.2f}%'.format(i / count * 100))
    return result


def generate_messages_trigrams(messages, count=5, start_word=None, min_word=4):
    trans, starts = trigram_from_messages(messages)
    i = 0
    result = []
    while i < count:
        msg = generate_with_trigrams(starts, trans, start_word)
        if len(words_from_message(msg)) > min_word:
            result.append(msg)
            i += 1
            if i % 200 == 0:
                print('{:.2f}%'.format(i / count * 100))
    return result


# more fun generator
def generate_story(messages, length=3, start_word=None):
    initial_start_word = start_word
    result = []
    i = 0
    restart_count = 0

    while i < length:
        try:
            # if there is no messages starting from start_word - rise Exception
            msg = generate_messages_bigrams(messages, 1, start_word, 2)[0]
        except:
            # start again
            i = 0
            result = []
            start_word = initial_start_word
            restart_count += 1
            continue

        words = words_from_message(msg)
        words = prepare_words(words)
        if i == 0:  # only for rist iteration, else will lead to duplication
            result.append(words[0])
        for prev, cur in zip(words, words[1:]):
            if prev not in ['.', '!', '?'] and cur != '.':
                result.append(cur)
        start_word = result[-1]
        result.append(',')
        i += 1
    print('restart count:', restart_count)
    return ' '.join(result)


def generate_messages_bigrams_totxt(messages, count=1000, start_word=None,
                                    min_word=3, filename='data/output.txt'):
    messages = generate_messages_bigrams(messages, count, start_word, min_word)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(messages))


def get_long_messages(messages, min_word=15):
    return [msg for msg in messages
            if len(words_in_document(msg)) > min_word]


def words_in_document(document):
    # return olny alphabetical words
    document = document.lower()
    words = re.findall(r'[а-яa-z]+', document)
    return [w for w in words]


def messages_to_UCI_bag_of_words(messages, min_word=15, name='1'):
    # exporting to UCI baf of words format
    messages = get_long_messages(messages, min_word)
    documents = [m.rstrip().lower() for m in messages]
    count_of_documents = len(documents)
    all_words = words_in_document(' '.join(documents))
    unique_words_count = len(set(all_words))
    all_words_count = len(all_words)

    dictionary = {}
    for i, word in enumerate(set(all_words)):
        dictionary[word] = i + 1

    UCI_bag_of_words = []
    for i, document in enumerate(documents):
        sentences = defaultdict(int)
        for word in words_in_document(document):
            sentences[word] += 1
        for word, count in sentences.items():
            if dictionary.get(word) is None:
                print(repr(word))
            UCI_bag_of_words.append([i + 1, dictionary.get(word), count])

    with open(name + 'data/_bag_of_word.txt', 'w') as f:
        f.write(str(count_of_documents) + '\n')
        f.write(str(unique_words_count) + '\n')
        f.write(str(all_words_count) + '\n')
        for line in UCI_bag_of_words:
            f.write(' '.join(map(str, line)) + '\n')

    with open(name + 'data/_dictionary.txt', 'w', encoding='utf-8') as f:
        for word, id in sorted(dictionary.items(), key=lambda x: x[1]):
            f.write(word + '\n\n')


def messages_to_json(messages, min_word=15, name='1'):
    # exporting to json format (for gensim)
    messages = get_long_messages(messages, min_word)
    documents = [m.rstrip().lower() for m in messages]
    documents = [words_in_document(document) for document in documents]
    print(len(documents))
    with open('data/' + name + '_messages.json', 'w') as f:
        json.dump(documents, f)


def get_syllables_num(word):
    vowels = {'а', 'е', 'ё', 'и', 'о', 'у', 'э', 'ю', 'я', 'ы'}
    num = 0
    for w in word:
        if w in vowels:
            num += 1
    return num


def generate_hokku(messages, start_word=None, count=3, gen_msgs=50):
    result = []
    i = 0
    # buffer of messages
    msgs = generate_messages_bigrams(messages, gen_msgs, start_word, 6)
    # position in buffer
    num = -1

    while i < count:
        num += 1
        # if buffer ended, generate new
        if num >= gen_msgs:
            msgs = generate_messages_bigrams(messages, gen_msgs, start_word, 6)
            num = 0

        words = words_from_message(msgs[num])
        words = prepare_words(words)
        if len(words) > 15:
            continue
        pos_cur_word = 0
        hokku = []
        is_ok = True

        for line_syllables in [5, 7, 5]:
            syll_count = 0
            line = []
            while syll_count < line_syllables and pos_cur_word < len(words):
                word = words[pos_cur_word]
                syll_count += get_syllables_num(word)
                pos_cur_word += 1
                line.append(word)
            if syll_count == line_syllables:
                hokku.append(line)
            else:
                is_ok = False
                break

        if is_ok:
            i += 1
            hokku = '\n'.join([' '.join(line) for line in hokku])
            result.append(hokku)
            if i % 10 == 0:
                print('{:.2f}%'.format(i / count * 100))

    return result


def generate_hokku_totxt(messages, count=100, start_word=None,
                         filename='data/hokku.txt'):
    hokkus = generate_hokku(messages, start_word, count)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(hokkus))


def main(argv):
    help_message = 'Usage: python generator.py -i <user_id>\n' +\
                   '-m for generating messages\n-h for generating hokku'
    if len(argv) == 0:
        print(help_message)
        sys.exit(1)
    try:
        opts, args = getopt.getopt(argv, 'mhi:')
    except getopt.GetoptError:
        print(help_message)
        sys.exit(1)

    is_msg = False
    is_hokku = False
    user_id = ''
    for opt, arg in opts:
        if opt == '-m':
            is_msg = True
        elif opt == '-h':
            is_hokku = True
        elif opt == '-i':
            user_id = str(arg)
        else:
            print(help_message)
            sys.exit(1)

    if not user_id:
        print('-i <user_id> is required argument!')
        sys.exit(1)

    if not (is_msg or is_hokku):
        print('-h or -m are required arguments!')
        sys.exit(1)

    print('Downloading messeges from {} ..'.format(user_id))
    my, other = download_messages(user_id)
    print(len(my), len(other))
    print('Download complete!')

    if is_msg:
        print('Generating messages..')
        generate_messages_bigrams_totxt(my, config.GENERATING_MESSAGE_COUNT,
                                        config.START_WORD,
                                        config.MIN_WORD_IN_MESSAGE,
                                        filename='my_generated.txt')
        generate_messages_bigrams_totxt(other, config.GENERATING_MESSAGE_COUNT,
                                        config.START_WORD,
                                        config.MIN_WORD_IN_MESSAGE,
                                        filename='{}_generated.txt'
                                                 .format(user_id))
        print('Complete!')
        sys.exit()
    elif is_hokku:
        print('Generating hokku..')
        generate_hokku_totxt(my, config.GENERATING_HOKKU_COUNT,
                             config.START_WORD,
                             filename='my_hokku.txt')
        generate_hokku_totxt(other, config.GENERATING_HOKKU_COUNT,
                             config.START_WORD,
                             filename='{}_hokku.txt'.format(user_id))
        print('Complete!')
        sys.exit()
    else:
        print('Usage: generator.py -i <user_id>\n' +
              '-m for generating messages\n-h for generating hokku')
        sys.exit(1)


if __name__ == '__main__':
    main(sys.argv[1:])
