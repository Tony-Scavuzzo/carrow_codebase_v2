""" 
This script allows carrow lab users to send code updates to each other in the linux shell upon login.
It interfaces with a json file named carrow_update_record.json, which is located at codebase/python_scripts/

Three behaviors are possible:
carrow_update           # updates the user with all updates that user has not seen
carrow_update filename  # adds a new update to the log
carrow_update n         # prints n most recent updates
"""

#####################
###Version Control###
#####################

# (since I will probably not convince the Carrow lab to use Github)
# Update this comment whenever edits are made.

edit_history = """
version Initials    Date            Summary
1.0     ARS         04-Aug-2023	    Initial draft is written - if a file is not specified, the user is updated. 
1.0                                 If a file is specified, the json file is updated.
1.1     ARS         04-Aug-2023     New users are added to json file
1.2     ARS         04-Aug-2023     Periodically suggests clearing out the json file
1.3     ARS         04-Sep-2023     User can now request n updates by providing a number as an argument
"""
version = edit_history.strip().split('\n')[-1].split()[0]


import json
import sys
import os


def read_json(file_path):
    """tries to read json file"""

    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print("File not found. Make sure the file path is correct.")
    except json.JSONDecodeError:
        print("Error decoding JSON data. Make sure the file contains valid JSON.")
    except Exception as e:
        print(f"An error occurred: {e}")
    return None


def write_json(path, data):
    """saves the json data"""

    with open(path, 'w') as json_file:
        json.dump(data, json_file, indent=4)


def update_user(user, data, path):
    """This code runs whenever a user logs in and 
    updates them if they have not seen the most recent update"""

    # if the user is already logged, prints all updates they haven't seen yet
    updates = data["updates"]
    if user in data["users"]:
        most_recent_update = data["users"][user]

        if most_recent_update < len(updates):
            print("------------------------------------------")
            print("Carrow Codebase Updates")
            i = most_recent_update
            for i in range(i, len(updates)):
                print(f'Update {i}:  {updates[i]}')
            print("------------------------------------------\n")

            data["users"][user] = len(updates)
            write_json(path, data)

    # adds new users to the json file and skips all old updates
    else:
        data["users"][user] = len(updates)
        write_json(path, data)

        print("------------------------------------------")
        print(f"{user} has been added to carrow_update log.")
        print("Updates to the carrow codebase will be printed here.")
        print("------------------------------------------\n")


def add_update(update_file, data, path):
    """This function adds a new update to the .json file"""

    try:
        with open(update_file) as file:
            new_update = file.read().rstrip('\n')

        data["updates"].append(new_update)
        print(f"new update added: {new_update}")
        write_json(path, data)

        if len(data["updates"]) > SUGGESTED_MAX:
            clear_updates(data, path, SUGGESTED_MAX)

    except FileNotFoundError:
        print(f"{update_file} not found")
    except Exception as e:
        print(f"An error occurred: {e}")


def clear_updates(data, path, SUGGESTED_MAX):
    """this function helps the user clear out old data from the json"""

    print(f"there are an excessive number of updates ({len(data['updates'])}).")
    print("Would you like to clear some? Enter y/n")
    if input(" > ").lower() == "y":
        print(f"how many jobs would you like to clear? Suggested: {SUGGESTED_MAX//2}")
        amount = int(input(" > "))
        data["updates"] = data["updates"][amount:]
        for user in data["users"]:
            data["users"][user] -= amount
        write_json(path, data)


def print_n_updates(data, n):
    """prints the n most recent updates from the data
    If n requested is more than the total amount, simply prints all"""

    end = len(data["updates"])
    start = end - n
    if start < 0:
        start = 0

    print("------------------------------------------")
    print("Carrow Codebase Updates")
    for i in range(start, end):
        print(f'Update {i}:  {data["updates"][i]}')
    print("------------------------------------------\n")


if __name__ == '__main__':
    SUGGESTED_MAX = 100
    user = sys.argv[2]
    path = f'{sys.argv[1]}/python_scripts/carrow_update_record.json'
    data = read_json(path)

    # handle arguuments
    if len(sys.argv) < 4:
        update_file = None
        n_updates = None
    elif len(sys.argv) == 4:
        if os.path.exists(sys.argv[3]):
            update_file = sys.argv[3]
            n_updates = None
        elif sys.argv[3].isdigit():
            n_updates = int(sys.argv[3])
            update_file = None
        elif sys.argv[3] == '-v' or sys.argv[3] == '-version':
            print(f'carrow_update version {version}')
            sys.exit(0)
        else:
            print("Error: Unrecognized argument")
            sys.exit(1)
    else:
        print("Error: There are too many arguments")
        sys.exit(1)

    # executes code according to which arguments are provided
    if update_file:
        add_update(update_file, data, path)
    elif n_updates:
        print_n_updates(data, n_updates)
    else:
        update_user(user, data, path)
