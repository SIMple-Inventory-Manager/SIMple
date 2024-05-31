## Create basic functionality

import os
import json

# Define Constants
SAVE_DATA_FOLDER = os.path.join(os.path.expanduser("~"), ".config/SIMple")
SAVE_DATA_FILE = os.path.join(SAVE_DATA_FOLDER, "itemlist.lcas")

#item_dict = {}
#items = {}
#items[item_id] = {"name": self.item_name, "Quantity": self.item_amount, "Threshold": self.item_min_amount, "Enabled": self.item_enabled, "Reorder": self.needs_reordered}

class Item:
    def __init__(self, info: list):
        self.item_id = int(info[0])
        self.item_name = info[1].replace("'", "")
        self.item_amount = int(info[2].replace("'", ""))
        self.item_min_amount = int(info[3].replace("'", ""))
        self.item_enabled = bool(info[4])
        self.needs_reordered = bool(info[5])

    def export(self):
        export_data[self.item_id] = {"name": self.item_name, "Quantity": self.item_amount, "Threshold": self.item_min_amount, "Enabled": self.item_enabled, "Reorder": self.needs_reordered}


def YES_NO():
    affirmative = ["", "yes", "y"]
    negative = ["n", "no"]
    answered = False
    while answered == False:
        answer = input("[Y/n] -> ")
        if answer.lower() in affirmative:
#            print("Answer appears to be 'yes'")
            answered = True
            return True

        elif answer.lower() in negative:
#            print("Answer appears to be 'no'")
            answered = True
            return False
            break
        else:
            print("That doesn't appear to be a valid response. Please try again.")

def addItem(force=False):
    if os.path.isfile(SAVE_DATA_FILE) and not force:
        items = loadInv()
        last_number = len(items)
        print(f"\t - Last item number appears to be {last_number}")
    else:
        last_number = 0

    item_number = int(last_number) + 1
    item_name = input("What is the item name? -> ")
    item_amount = input("How many do you have on hand? -> ")
    item_min_amount = input("What is the minimum amount allowed before restock? -> ")

    item = Item([item_number, item_name, item_amount, item_min_amount, False])
    with open(SAVE_DATA_FILE, 'a') as save_file:
        save_file.write(str(item))
        print("Item saved successfully.")

def initialize():
    try:
        os.mkdir(SAVE_DATA_FOLDER)
    except PermissionError:
        print(f"It appears you do not have appropriate permissions to {SAVE_DATA_FOLDER}. Please contact your administrator.")
    except FileExistsError:
        print("Folder already exists. Moving to save file.")
    print("Please create an item to initialize the database.")
    addItem()

def loadInv():
    print("Attempting to load items")
    with open(SAVE_DATA_FILE, 'r') as save_file:
        items = save_file.readlines()


    if len(items) >= 1:
        return items
    else:
        print("There don't appear to be any items in this file. Would you like to add one?")
        make_new = YES_NO()
        if make_new:
            addItem(True)
        else:
            print("An error has occurred. Please contact your administrator.")
            exit()

def itemEditor(item_to_edit):
    print(f"Existing info:\n\tName: {item_to_edit.item_name}\n\tQTY: {item_to_edit.item_amount}")
    menu = ["Remove one", "Remove more than one", "Add one", "Add more than one"]

    if item_to_edit.item_amount <= item_to_edit.item_min_amount:
        print("Alert! This item should be reordered!")
        menu.append("Mark as reordered")
    print("Options:\n\t1. Remove one\n\t2. Remove more than one\n\t3. ")

def invMan():
    if not os.path.isdir(SAVE_DATA_FOLDER) or not os.path.isfile(SAVE_DATA_FILE):
        print("This appears to be the first time running this program. Would you like to create the necessary files?")
        make_new = YES_NO()
        if make_new:
            initialize()
        else:
            print("Okay, goodbye.")
            quit()

    #test_item_1 = Item(1, "Provaxin", 30, 10)
    #test_item_2 = Item(2, "Anatolin", 24, 5)
    #test_items = [test_item_1, test_item_2]

    items = loadInv()
    visual_items = []
    print("ID    Name \t\t On Hand")
    number = 1
    for item in items:
        if number < 30:
            item = Item(item.split(","))
            visual_items.append(item)
            print(f"{number}. {item.item_name} \t\t {item.item_amount}")
            number += 1
    answered = False
    while answered == False:
        print("Which would you like to edit? ")
        item_to_edit = input(f"[1 .. {number-1}] -> ")
        try:
            item_to_edit = int(item_to_edit)
        except ValueError:
            print("This does not appear to be a number. Please try again.")
        if item_to_edit < number:
            itemEditor(visual_items[item_to_edit-1])



def menu():
    menu_items = ["Enter Inventory Manager", "Add Inventory Items", "Exit"]

    decided = False
    while decided == False:
        choice_int = 1
        for choice in menu_items:
            print(f"{choice_int}. {choice}")
            choice_int += 1
        choice = input(f"Please select an option [1 .. {len(menu_items)}] -> ")

        match choice:
            case "1":
                decided = True
                invMan()
            case "2":
                decided = True
                addItem()
            case "3":
                decided = True
                exit()
            case _:
                print("That doesn't seem to be a valid option. Please try again.")

while __name__ == "__main__":
    menu()
