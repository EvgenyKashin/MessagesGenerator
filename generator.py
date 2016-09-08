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
import config

url_for_token = 'https://oauth.vk.com/authorize?client_id=5298215&scope=messages&redirect_uri=https://oauth.vk.com/blank.html&display=page&response_type=token'
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
    return my, other


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
    transitions = defaultdict(list)
    start_words = []
    for msg in messages:
        words = words_from_message(msg)
        words = prepare_words(words)
        if len(words) > 2:
            start_words.append(words[0])
            bigrams = zip(words, words[1:])
            for prev, current in bigrams:
                transitions[prev].append(current)
    return transitions, start_words


@memo_list
def trigram_from_messages(messages):
    transitions = defaultdict(list)
    start_words = []
    for msg in messages:
        words = words_from_message(msg)
        words = prepare_words(words)
        if len(words) > 2:
            start_words.append(words[0])
            trigrams = zip(words, words[1:], words[2:])
            for prev, current, next in trigrams:
                transitions[(prev, current)].append(next)
    return transitions, start_words


def generate_with_bigrams(start_words, transitions, start_word=None):
    current = random.choice(start_words)
    if start_word:
        current = start_word
    result = [current]
    while True:
        next_word_candidates = transitions[current]
        if len(next_word_candidates) > 0:
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
        current = start_word
    result = [current]
    while True:
        next_word_candidates = transitions[(prev, current)]
        if len(next_word_candidates) > 0:
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
    return result


# TODO
def generate_story(messages, length=10, start_word=None):
    trans, starts = bigram_from_messages(messages)
    result = []
    for i in range(length):
        cur = generate_with_bigrams(starts, trans, start_word)
        words = words_from_message(cur)
        start_word = words[-1]
        result.extend(words[:-1])
    return ' '.join(result)


def generate_messages_bigrams_totxt(messages, count=1000, start_word=None,
                                    min_word=3, filename='data/output.txt'):
    messages = generate_messages_bigrams(messages, count, start_word, min_word)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(messages))


def get_long_messages(messages, min_word=15):
    return [msg for msg in messages
            if len(words_in_document(msg)) > min_word]


def words_in_document(document):
    document = document.lower()
    words = re.findall(r'[а-яa-z]+', document)
    return [w for w in words]


def messages_to_UCI_bag_of_words(messages, min_word=15, name='1'):
    messages = get_long_messages(messages, min_word)
    documents = [m.rstrip().lower() for m in messages]
    count_of_documents = len(documents)
    all_words = words_in_document(' '.join(documents))
    unique_words_count = len(set(all_words))
    all_words_count = len(all_words)
    # print(count_of_documents, all_words_count, unique_words_count)

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
            f.write(word + '\n')


def messages_to_json(messages, min_word=15, name='1'):
    messages = get_long_messages(messages, min_word)
    documents = [m.rstrip().lower() for m in messages]
    documents = [words_in_document(document) for document in documents]
    print(len(documents))
    with open('data/' + name + '_messages.json', 'w') as f:
        json.dump(documents, f)


if __name__ == '__main__':
    if (len(sys.argv) > 1):
        # read user_id from command line argument
        user_id = str(sys.argv[1])
        print('Downloading messeges from {} ..'.format(user_id))
        my, other = download_messages(user_id)
        print('Download complete!')
        print('Generating messages..')
        generate_messages_bigrams_totxt(my, config.GENERATING_MESSAGE_COUNT,
                                        config.START_WORD,
                                        config.MIN_WORD_IN_MESSAGE,
                                        filename='my_generated.txt')
        generate_messages_bigrams_totxt(my, config.GENERATING_MESSAGE_COUNT,
                                        config.START_WORD,
                                        config.MIN_WORD_IN_MESSAGE,
                                        filename='{}_generated.txt'
                                                 .format(user_id))
        print('Complete!')
