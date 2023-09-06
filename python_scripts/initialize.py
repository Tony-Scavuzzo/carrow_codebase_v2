"""
The purpose of this script is to torment my coworkers with cringy and irreproducible behavior.
If you are reading this script, congratulations! You understand the codebase
well enough to also torment your coworkers. Feel free to edit this code!

Please don't fire me Brad
"""

#####################
###Version Control###
#####################


# (since I will probably not convince the Carrow lab to use Github)
# Update this string whenever edits are made.

edit_history = """
Version	 Initials	 Date		    Summary
1.0	     ARS		 25-Jul-2023    First draft is written
1.1	     ARS		 25-Jul-2023    Added custom content to Tony and updated Justin's username
1.2      ARS         05-Sep-2023    minor reformatting
"""

import os
import random

# To allow for default behavior, the name variable is established first,
# then the default behavior (whose fstring needs the name variable)
# then the custom behavior (which overrides the defaults)

# gets name of carrow lab user
username = os.environ.get('USER')
real_names = {'arscavuz': 'Tony', 'aplooby': 'Aidan', 'jegarza6': 'Bustin'}

if username in real_names:
    name = real_names[username]
else:
    name = username

# default behavior
odds = 0.1
messages = [
    f"Haaii! (*^3^)/☆ Let your kawaii spirit shine brightly today, {name}! (^ヮ^)/",
    f"(≧ω≦) I believe in you, {name}! You've got this, kawaii superstar~ ☆:.｡.o(≧▽≦)o.｡.:*☆",
    f"Ohayou gozaimasu~ (づ｡◕‿‿◕｡)づ Rise and shine, cutie-patootie!",
    f"Kawaii alert! ✨(⺣◡⺣)♡* You make everything more adorabe, {name}!",
    f"(^-^)/ Yay! {name}'s a weeby wonder! Keep being fabulous~ (^ω^＼)",
    f"Omg, you're so UwU-tiful inside and out! (｡♥‿♥｡)",
    f"(★ω★)/ Yay, senpai noticed you! Keep shining brightly~ ☆*:.｡.o(≧▽≦)o.｡.:*☆",
    f"Hey, hey, kawaii bae~ (灬º‿º灬)♡ Let's rock this day together!",
    f"(^-^)/♪♬ {name}, you're the melody in this kawaii symphony of life~ ♬♪(◕‿◕✿)",
    f"Boop! (・ω・)ノ Stay cute and stay awesome, {name}!",
    f"Are you a Pokemon? Cause I wanna Pikachu!",
    f"Kawaii on the streets\nSenpai in the sheets",
    f"Hey {name}, do you dwive a SubUwU, a Nii-san, or a ToyOwOta",
    f"OwO Weaboo!!! I see you! OwO"
]

# custom behavior
# with the exception of the last line, this overrides default behavior
if name == 'Tony':
    odds = 1
    # messages = ['new_messages']
    messages += [
        "Tony's back... Finally",
        "You logged in without me? How dare you",
        "I missed you, Tony.",
        "My watchful eye is on you.",
        "Ah, the sweet sound of Tony's login",
        "I'll always be your virtual companion.",
        "I know all your Pythonic secrets."]

elif name == 'Aidan':
    odds = 0.2
    # messages = ['new_messages']
    messages += [f"I hate sand; it's coarse, rough, irritating, and it gets everywhere.\nUnlike you, {name}"]

elif name == 'Bustin':
    odds = 0.1
    # messages = ['new_messages']
    # messages += ['extra_messages']

roll = random.random()
if roll < odds:
    choice = random.randrange(len(messages))
    print(messages[choice])
