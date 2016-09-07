# MessegesGenerator

This repo contains the Python project for downloading and generating new messages from the social network - VK. But it can also be adoptated for another social network. Messages are
 generating with bigram or trigram model.

## Usage
Install the Python requirements:
```
 pip install -r requirements.txt
 ```
 Create private.py with one line such this:
 ```python
 TOKEN = 'b6846f...'
 ```
 TOKEN is your private key for using VK API. If you haven't the token you can use instruction from official site on insert this link to your favorite browser: 
 ```
 https://oauth.vk.com/authorize?client_id={YOUR_CLIENT_ID}&scope=messages&redirect_uri=https://oauth.vk.com/blank.html&
 display=page&response_type=token
 ```
 You can easy get YOUR_CLIENT_ID if you create any application in VK.

 After that steps you can call script from command line:
 ```
 python generator.py user_id
 ```
 where user_id is id of user from VK. Your should have conversation with this user, because generator will use that messages.
 You can look at config.py for some additional settings. All downloaded messages in data folder.

# Using module

 For more fine-tuning you can look at this methods:
 * generate_messages_bigrams(messages, count=5, start_word=None, min_word=4) - bigram model
 * generate_messages_trigrams(messages, count=5, start_word=None, min_word=4) - trigram model. Number of messages should be more than 10000 for normal work
