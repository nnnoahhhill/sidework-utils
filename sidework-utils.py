#!/usr/bin/env python3

import argparse
import os
import requests
import json
from simple_term_menu import TerminalMenu
from enum import Enum
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from scipy.fft import fft, fftfreq
import tkinter as tk
from tkinter import filedialog
import sys
import time
from datetime import datetime
import pytz
import re

class target(Enum):
    main          = 1
    solenoid      = 2
    pump          = 5
    nozzle        = 6
    ice_dispenser = 7
    cooling       = 9
    conveyor      = 10
    qr_reader     = 11

class updateTargetEnum(Enum):
    Main     = 0
    Solenoid = 1
    Pump     = 2
    Nozzle   = 3
    Cooling  = 4
    QR       = 5

def setup_argpase():
    parser = argparse.ArgumentParser(prog='sidework-utils', 
                                     description='Interactive tools for working with Sidework machines', 
                                     formatter_class=lambda prog: argparse.HelpFormatter(prog,max_help_position=35),
                                     epilog='~ with great power comes great responsibility ~')
    parser.add_argument('-k', '--key', metavar='KEY', required=True, help='api key stored in a file')
    parser.add_argument('-t', '--token', metavar='TOKEN', required=True, help="auth token stored in a file")
    parser.add_argument('--list-latest-apps', action='store_true', help='prints most recent deployed firmware applications, sorted by target')
    parser.add_argument('--target', metavar='TARGET', type=str, help=' ^^ list only recent apps for provided target (qr_reader, pump, etc)')
    parser.add_argument('--machine-status', metavar='ID', type=int, help='view previous, current and queued applications for specified machine ID')
    parser.add_argument('--list-all-machines', action='store_true', help='prints list of all valid machine names with ID and serial numbers')
    parser.add_argument('--gregorys', action='store_true', help=' ^^ pass this flag to only list all gregorys org machines')
    parser.add_argument('--backbar', action='store_true', help=' ^^ pass this flag to only list backbar org machines')
    parser.add_argument('--name-filter', metavar='FILTER', type=str, help=' ^^ pass this flag to filter listed machines by checking names')
    parser.add_argument('--list-logs', metavar='ID', type=int, help='returns URLs to logs of machine specified by ID number')
    parser.add_argument('--graph-temps', metavar='ID', type=int, help='graph recent temperature data for machine specified by ID number')
    parser.add_argument('--update-fw', action='store_true', help='select machine(s) for updating and fw per target')
    parser.add_argument('--notes-filter', metavar='NOTES', type=str, help='filter fw apps by notes (pass PROD to filter by production releases)')
    parser.add_argument('--clear', action='store_true', help='select machine(s) with pending fw updates to cancel')

    return parser.parse_args()

def read_file(file):
    with open(file, "r") as f:
        return f.readline()
    
def write_file(file, content):
    with open(file, "w") as f:
        f.write(content)

def append_file(file, content):
    with open(file, "a") as f:
        f.write(content)

def read_key_and_token(args):
    with open(args.key) as k:
        apikey = k.readline().strip("\n")
    with open(args.token) as t:
        authtoken = t.readline().strip("\n")
    return apikey, authtoken

def print_at_bottom(text):
    sys.stdout.write("\033[s")
    sys.stdout.write("\033[999B\033[1E")
    sys.stdout.write("\033[K" + text)
    sys.stdout.write("\033[u")
    sys.stdout.flush()

def print_at_top(text):
    sys.stdout.write("\033[1;1H")
    sys.stdout.flush()
    sys.stdout.write("\033[K" + text)
    sys.stdout.flush()

def clear_screen():
    if os.name == 'posix': 
        os.system('clear')
    elif os.name == 'nt':
        os.system('cls')

def get_list_of_all_machines():
    headers = {'Authorization' : str(authtoken), 'x-api-key': str(apikey)}
    url = "https://api.backbar.com/machine"
    response = requests.request("GET", url, headers=headers)
    machine_info = json.loads(response.text)
    return machine_info

def print_machine_info(machine):
    print(machine['name'])
    print("   ID: " + str(machine['id']))
    print("   Serial Number: " + str(machine['serialNumber']) + "\n")

def print_app_info(app):
    print("Target: " + str(app['type']['name']) + " || Version: " + str(app['fwMajor']) + "." + str(app['fwMinor']) + "." + str(app['fwPatch']) + ' || Notes: ' + str(app['notes']))
    print("   URL: " + str(app['filePath']))
    print("\n")

def wait_for_specific_input(expected_input):
    while True:
        user_input = input(f"Enter '{expected_input}' to continue if selected option(s) are OK ('q' to quit): ")
        if user_input.lower() == expected_input.lower():
            break
        if user_input.lower() == 'q':
            quit()

def get_list_of_apps(target, notes):
    headers = {'Authorization' : str(authtoken), 'x-api-key': str(apikey)}
    url = "https://api.backbar.com/application"
    response = requests.request("GET", url, headers=headers)
    apps = json.loads(response.text)
    if target:
        apps = [item for item in apps if item['type'].get('name').lower() == target.lower()]
    if notes is not None and notes == "PROD":
        apps = [item for item in apps if item['notes'] == ""]
    elif notes is not None:
        apps = [item for item in apps if item['notes'] == notes]
    return apps

def list_latest_apps(args):
    print('\nRetrieving list of most recently deployed applications...\n')
    apps = get_list_of_apps(args.target, None)
    for app in apps[-10:]:
        print_app_info(app)

def list_all_machines(args):
    print('\nRetrieving all machines...\n')
    machine_info = get_list_of_all_machines()
    for machine in machine_info:
        if args.gregorys:
            if (machine['location']['organization']['name'] == 'Gregorys Coffee'):
                print_machine_info(machine)
        elif args.backbar:
            if (machine['location']['organization']['name'] == 'BackBar'):
                print_machine_info(machine)
        elif args.name_filter:
            if (args.name_filter in machine['name']):
                print_machine_info(machine)
        else:
            print_machine_info(machine)

def list_logs(args):
    print("\nRetrieving most recent logs from Machine ID " + str(args.list_logs) + "...\n")
    headers = {'Authorization' : str(authtoken), 'x-api-key': str(apikey)}
    payload = {}
    url = "https://api.backbar.com/log?machineId="
    url += str(args.list_logs)
    url += "&count=10"
    response = requests.request("GET", url, headers=headers, data=payload)
    logfiles = json.loads(response.text)

    menu_title = "~ ~ select log(s) you want to download (press 'space' to select, 'enter' to confirm, 'q' to quit) ~ ~\n"
    menu_items = []
    for log in logfiles['data']:
        date = str(log['addDT'])
        option = date + " File: " + log['fileName']
        menu_items.append(option)

    terminal_menu = TerminalMenu(
        menu_entries=menu_items,
        title = menu_title,
        clear_screen = True,
        cycle_cursor = False,
        multi_select = True
    )

    menu_entry_indexes = terminal_menu.show()
    for menu_entry_index in menu_entry_indexes:
        if menu_entry_index is not None and menu_entry_index < len(logfiles['data']):
            selected_log = logfiles['data'][menu_entry_index]
            log = requests.request("GET", selected_log['fileUrl'])
            write_file(selected_log['fileName'], log.text)
            print("*** Log saved to " + selected_log['fileName'] + " ***\n")

# TODO: adjust argparse to take n parameters and print status for n machines
def get_machine_status(args, f):
    print("\nRetrieving firmware status for Machine ID " + str(args.machine_status) + "...\n", file=f)
    headers = {'Authorization' : str(authtoken), 'x-api-key': str(apikey)}
    url = "https://api.backbar.com/board?machineId="
    url += str(args.machine_status)
    response = requests.request("GET", url, headers=headers)
    boards_full_info = json.loads(response.text)
    machine_name = boards_full_info[0]['machine']['name']
    
    boards_status = [
        ["Target", "PCB Version", "Status", "Current FW", "Queued FW", "Previous FW"]
    ]

    for board in boards_full_info:
        if board['scheduled'] == None:
            queued = "N/A"
        else:
            queued = str(board['scheduled']['fwMajor']) + "." + str(board['scheduled']['fwMinor']) + "." + str(board['scheduled']['fwPatch']) + " " + str(board['scheduled']['notes'])
        if board['type']['name'] == "Pump":
            board_num = "" + str(board['protocolId'])
        else:
            board_num = ""
        boards_status.append([
            board['type']['name'] + " " + str(board_num),
            str(board['pcbMajor']) + "." + str(board['pcbMinor']) + "." + str(board['pcbPatch']),
            board['status'],
            str(board['application']['fwMajor']) + "." + str(board['application']['fwMinor']) + "." + str(board['application']['fwPatch']) + " " + str(board['application']['notes']),
            queued,
            str(board['previous']['fwMajor']) + "." + str(board['previous']['fwMinor']) + "." + str(board['previous']['fwPatch']) + " " + str(board['previous']['notes'])
        ])
    
    col_widths = [max(len(str(item)) for item in col) for col in zip(*boards_status)]
    header = boards_status[0]

    print("*  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  * ", file=f)
    print("Application status for: " + machine_name, file=f)
    print("*  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  * \n ", file=f)

    for i, item in enumerate(header):
        print(item.ljust(col_widths[i] + 4), end="", file=f)
    print("",file=f)
    for width in col_widths:
        print('-' * (width + 4), end="", file=f)
    print("", file=f)
    for row in boards_status[1:]:
        for i, item in enumerate(row):
            print(item.ljust(col_widths[i] + 4), end="", file=f) 
        print("", file=f)
    print("", file=f)
    
def graph_temps(args):
    print("\nGraphing recent temperatures for Machine ID " + str(args.graph_temps) + "...")
    headers = {'Authorization' : str(authtoken), 'x-api-key': str(apikey)}
    payload = {}
    url = "https://api.backbar.com/log?machineId="
    url += str(args.graph_temps)
    url += "&count=50"
    response = requests.request("GET", url, headers=headers, data=payload)
    logfiles = json.loads(response.text)

    menu_title = "~ ~ select temperature file you want to graph and download (press 'q' to quit) ~ ~\n"
    menu_items = []
    temp_logs = []
    for log in logfiles['data']:
        if "TEMPERATURE" in log['fileName']:
            date = str(log['addDT'])
            option = "Date: " + date + " File: " + log['fileName']
            menu_items.append(option)
            temp_logs.append(log)

    terminal_menu = TerminalMenu(
        menu_entries=menu_items,
        title = menu_title,
        clear_screen = True,
        cycle_cursor = False
    )

    menu_entry_index = terminal_menu.show()
    if menu_entry_index is not None and menu_entry_index < len(logfiles['data']):
        selected_log = temp_logs[menu_entry_index]
        log = requests.request("GET", selected_log['fileUrl'])

    log = requests.request("GET", selected_log['fileUrl'])
    write_file(selected_log['fileName'], log.text)
    print("\n*** Full temp log saved to " + selected_log['fileName'] + " ***\n")
    print("Graphing temperature data...\n")
    plot_csv_data(selected_log['fileName'], args.graph_temps, selected_log['addDT'])

def sanitize_temp_data(file_path):
    with open(file_path, 'r') as f:
        data = f.read()
        cleaned_data = re.sub(r'(?<!\,)2024', r',2024', data)
    with open(file_path, 'w') as f:
        f.write(cleaned_data)

def plot_csv_data(file_path, id, date):
    root = tk.Tk()
    root.withdraw()
    sanitize_temp_data(file_path)
    try:
        data = pd.read_csv(file_path)
        data['Timestamp'] = pd.to_datetime(data['Timestamp'])
        data.set_index('Timestamp', inplace=True)

        plt.figure(figsize=(14, 7))
        plt.plot(data.index, data['In 1 Temp'], label='Upper Temperature')
        plt.plot(data.index, data['In 2 Temp'], label='Lower Temperature')
        plt.plot(data.index, data['Out Temp'], label='Outside Temperature')
        plt.xlabel('Timestamp')
        plt.ylabel('Temperature (F)')
        plt.title('Refrigerator Performance, Machine ID: ' + str(id) + ", Date: " + date)
        plt.ylim(10, 100)
        plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=4))
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        plt.gca().xaxis.set_minor_locator(mdates.HourLocator(interval=1))
        plt.grid(which='major', linestyle='-', linewidth='0.5', color='gray')
        plt.minorticks_on()
        plt.grid(which='minor', linestyle=':', linewidth='0.5', color='gray')
        plt.legend()
        plt.show()

    except pd.errors.ParserError:
        print("Error: Failed to parse the CSV file.")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

def present_list_of_machines(machines):
    menu_title = "~ select machine(s) to update (press 'space' to select, 'enter' to confirm) ~ ~\n"
    raw_menu_options = []
    for machine in machines:
        option = {
            "name"   : machine['name'],
            "id"     : str(machine['id']),
            "serial" : str(machine['serialNumber'])
        }
        raw_menu_options.append(option)
    max_length = max(len(option["name"]) for option in raw_menu_options)
    max_length_id = max(len(option["id"]) for option in raw_menu_options)
    menu_options = [
        option['name'].ljust(max_length) + "  -   ID: " + option['id'].ljust(max_length_id) + "   Serial #: " + option['serial']
        for option in raw_menu_options
    ]
    menu_options.append("*** QUIT (quit application and return to terminal)")

    terminal_menu = TerminalMenu(
        menu_entries=menu_options,
        title = menu_title,
        clear_screen = True,
        cycle_cursor = True,
        multi_select=True
    )

    selected_options = terminal_menu.show()
    selected_machines = []

    if selected_options is not None:
        if len(menu_options) - 1 in selected_options:
            sys.exit()
        selected_machines = [machines[index] for index in selected_options if menu_options[index].strip()]
        print("\033[1mSelected machines:\033[0m\n")
        for machine in selected_machines:
            print("* " + machine['name'])
        print("\n")
        time.sleep(0.5)
        for i in range(7):
            print_at_bottom("\033[1m!!!!!! REVIEW LIST CAREFULLY !!!!!!!\033[0m")
            time.sleep(0.3)
            print_at_bottom("")
            time.sleep(0.2)
        print_at_bottom("\033[1m!!!!!! REVIEW LIST CAREFULLY !!!!!!!\033[0m")
        time.sleep(0.5)
        wait_for_specific_input("yes")
        print("\nMachines confirmed, continuing to firmware application selections...\n")
        return selected_machines
    else:
        print("No option selected, quitting...\n")
        quit()

def present_list_of_apps(list_of_apps):
    target = list_of_apps[0]['type']['name']
    menu_title = "~ select " + target.upper() + " firmware version to queue ~ ~\n"
    raw_menu_options = []
    for app in list_of_apps:
        if app['notes'] is not None and app['notes'] != "" and len(app['notes']) > 2:
            notes = "-" + app['notes']
        else:
            notes = " !!!! PROD RELEASE - no notes !!!!"
        option = {
            "target" : target,
            "version": str(app['fwMajor']) + "." + str(app['fwMinor']) + "." + str(app['fwPatch']),
            "notes"  : notes
        }
        raw_menu_options.append(option)
    max_length = max(len(option["version"]) for option in raw_menu_options)
    menu_options = [
        option['target'] + "  -  " + option['version'].ljust(max_length) + option['notes']
        for option in raw_menu_options
    ]
    menu_options.append("*--- NONE ---* (do not update firmware for this target)")
    menu_options.append("**** QUIT **** (quit and return to terminal)")

    terminal_menu = TerminalMenu(
        menu_entries=menu_options,
        title = menu_title,
        clear_screen = True,
        cycle_cursor = True
    )

    try:
        selected_option_index = terminal_menu.show()
        if selected_option_index is not None:
            if selected_option_index == len(menu_options) - 1:
                sys.exit()
            if selected_option_index == len(menu_options) - 2:
                selected_app = "None"
                print("\033[1mSelected application for " + target + ":\033[0m\n")
                print("  **  No application selected for " + target + "\n")
            else:
                selected_app = list_of_apps[selected_option_index]
                print("\033[1mSelected application for " + target + ":\033[0m\n")
                print_app_info(selected_app)
            time.sleep(0.4)
            for i in range(3):
                print_at_bottom("\033[1m!!!!!! REVIEW APPLICATION CAREFULLY !!!!!!!\033[0m")
                time.sleep(0.2)
                print_at_bottom("")
                time.sleep(0.1)
            print_at_bottom("\033[1m!!!!!! REVIEW APPLICATION CAREFULLY !!!!!!!\033[0m")
            time.sleep(0.4)
            wait_for_specific_input("yes")
            print("\nApplication confirmed, continuing...\n")
            return selected_app
    except KeyboardInterrupt:
        sys.exit(0)

def print_app_for_update_confirmation(target, app):
    if app['notes'] is not None and app['notes'] != "" and len(app['notes']) > 2:
        notes = "-" + app['notes']
    else:
        notes = " !!!! PROD RELEASE - no notes !!!!"
    print("* " + target + ": " + str(app['fwMajor'])  
                        + "." + str(app['fwMinor'])  
                        + "." + str(app['fwPatch']) 
                        + notes)

def print_all_app_details(all_apps):
    app_list = []
    for app in all_apps:
        if app != "None":
            if app['notes'] is not None and app['notes'] != "" and len(app['notes']) > 2:
                notes = app['notes']
            else:
                notes = " !!!! PROD RELEASE - no notes !!!!"
            app_list.append([
                app['type']['name'],
                str(app['fwMajor']) + "." + str(app['fwMinor']) + "." + str(app['fwPatch']),
                notes
            ])
    col_widths = [max(len(row[i]) for row in app_list) for i in range(len(app_list[0]))]
    headers = ["Target", "Version", "Notes"]
    header_line = " ".join(headers[i].ljust(col_widths[i] + 3) for i in range(len(headers)))
    print(header_line)
    print("-" * len(header_line))
    for row in app_list:
        for i, item in enumerate(row):
            print(item.ljust(col_widths[i] + 4), end="")
        print()

def convert_app_record(full_board_rec, new_app):
    if new_app == "None":
        full_board_rec['scheduled'] = None
        full_board_rec['status'] = "Installed"
        return full_board_rec
    else:
        new_app["version"] = ""
        full_board_rec['scheduled'] = new_app
        full_board_rec['status'] = "Pending"
        return full_board_rec

def update_board_records(apps, machines, args, fname):
    print("Queuing firmware application updates to all targets on all selected machines...\n")
    headers = {'Authorization' : str(authtoken), 'x-api-key': str(apikey)}
    general_boards_url = "https://api.backbar.com/board?machineId="
    for machine in machines:
        print("** Updating boards on " + machine['name'])
        append_file(fname, "** Updating boards on " + machine['name'] + "\n")
        curr_machine_boards_url = general_boards_url + str(machine['id'])
        response = requests.request("GET", curr_machine_boards_url, headers=headers)
        curr_machine_boards = json.loads(response.text)
        fail = False
        for board in curr_machine_boards:
            if board['type']['name'] != "Conveyor" and board['type']['name'] != "Ice Dispenser" and board['type']['name'] is not None:
                deploy_str = "     Deploying application to target: " + board['type']['name']
                print(deploy_str)
                append_file(fname, deploy_str)
            else:
                continue
            if board['type']['name'] == "Main" and updateTargetEnum.Main.value < len(apps) - 1:
                board = convert_app_record(board, apps[updateTargetEnum.Main.value])
            if board['type']['name'] == "Solenoid" and updateTargetEnum.Solenoid.value < len(apps) - 1:
                board = convert_app_record(board, apps[updateTargetEnum.Solenoid.value])
            if board['type']['name'] == "Pump" and updateTargetEnum.Pump.value < len(apps) - 1:
                board = convert_app_record(board, apps[updateTargetEnum.Pump.value])
            if board['type']['name'] == "Nozzle" and updateTargetEnum.Nozzle.value < len(apps) - 1:
                board = convert_app_record(board, apps[updateTargetEnum.Nozzle.value])
            if board['type']['name'] == 'Cooling' and updateTargetEnum.Cooling.value < len(apps) - 1:
                board = convert_app_record(board, apps[updateTargetEnum.Cooling.value])
            if board['type']['name'] == 'QR Reader' and updateTargetEnum.QR.value < len(apps) - 1:
                board = convert_app_record(board, apps[updateTargetEnum.QR.value])
            curr_board_url = "https://api.backbar.com/board/" + str(board['id'])
            response = requests.request("PUT", curr_board_url, headers=headers, json=board)
            if response.status_code != 200:
                fail = True
            print("     HTTP response: " + str(response.status_code) + "\n")
            append_file(fname, "\n        HTTP response: " + str(response.status_code))
            append_file(fname, "\n        HTTP text:     " + response.text + "\n\n")

    for machine in machines:
        f = open(fname, 'a')
        args.machine_status = machine['id']
        get_machine_status(args, f)
        f.close()
    if fail:
        print("!!! !!! one or more operations failed, check report !!! !!!\n")
        append_file(fname, "!!! !!! one or more operations failed, check report !!! !!!\n")

def generate_fw_update_report(selected_machines, all_apps):
    pst = pytz.timezone('America/Los_Angeles')
    now_utc = datetime.now(pytz.utc)
    now_pst = now_utc.astimezone(pst)
    header  = "***  Firmware Update Report   ***  ***  ***  ***  ***  ***  ***  ***\n"
    date    = "***\n***  Date: " + now_pst.strftime("%Y-%m-%d %H:%M:%S %Z %z")
    divider = "\n***  ***  ***  ***  ***  ***  ***  ***  ***  ***  ***  ***  ***  ***\n" 
    fname   = "FW-UPDATE-REPORT_" + now_pst.strftime("%Y-%m-%d_%H-%M-%S_%Z%z" + ".txt")
    write_file(fname, header+date+divider)
    append_file(fname, "\n-- List of Machines -- -- -- -- -- -- -- \n\n")
    for machine in selected_machines:
        append_file(fname, "* " + machine['name'] + "\n")
    append_file(fname, "\n\n\n-- List of Firmware Apps  -- -- -- -- --  \n\n\n")
    app_list = []
    for app in all_apps:
        if app != "None":
            if app['notes'] is not None and app['notes'] != "" and len(app['notes']) > 2:
                notes = app['notes']
            else:
                notes = "!!!! PROD RELEASE - no notes !!!!"
            app_list.append([
                app['type']['name'],
                str(app['fwMajor']) + "." + str(app['fwMinor']) + "." + str(app['fwPatch']),
                notes,
                str(app['filePath'])
            ])
    col_widths = [max(len(row[i]) for row in app_list) for i in range(len(app_list[0]))]
    headers = ["Target", "Version", "Notes", "URL"]
    header_line = " ".join(headers[i].ljust(col_widths[i] + 3) for i in range(len(headers)))
    append_file(fname, header_line + "\n")
    append_file(fname,"-" * len(header_line) + "\n")
    for row in app_list:
        for i, item in enumerate(row):
            append_file(fname, item.ljust(col_widths[i] + 4))
        append_file(fname, "\n")
    append_file(fname, "\n\n***  Results   ***  ***  ***  ***  ***  ***  ***  ***  ***  ***  ***\n\n")
    return fname

def update_fw(args):
    print("\nStarting firmware update interface...\n")
    filter_str = "with filter 'Gregorys Coffee'...\n" if args.gregorys else \
                 "with filter 'BackBar'...\n" if args.backbar else \
                  "with filter '" + str(args.name_filter) + "'...\n" if args.name_filter else "...\n"
    print("Retrieving list of machines " + filter_str)
    full_machines_list = get_list_of_all_machines()
    filtered_machines_list = []
    for machine in full_machines_list:
        if args.gregorys:
            if (machine['location']['organization']['name'] == 'Gregorys Coffee'):
                filtered_machines_list.append(machine)
        elif args.backbar:
            if (machine['location']['organization']['name'] == 'BackBar'):
                filtered_machines_list.append(machine)
        elif args.name_filter:
            if (args.name_filter in machine['name']):
                filtered_machines_list.append(machine)
        else:
            filtered_machines_list.append(machine)

    notes_filter  = args.notes_filter if args.notes_filter else None
    notes_filter_str = ", filtered by notes '" + notes_filter + "'...\n" if notes_filter is not None else "...\n"
    print("Retrieving lists of recent applications, organized per target" + notes_filter_str)
    main_apps     = get_list_of_apps(target.main.name, notes_filter)
    solenoid_apps = get_list_of_apps(target.solenoid.name, notes_filter)
    pump_apps     = get_list_of_apps(target.pump.name, notes_filter)
    nozzle_apps   = get_list_of_apps(target.nozzle.name, notes_filter)
    cooling_apps  = get_list_of_apps(target.cooling.name, notes_filter)
    qr_apps       = get_list_of_apps("QR Reader", notes_filter)

    selected_machines     = present_list_of_machines(filtered_machines_list)
    if args.clear:
        print("\nClearing queued firmware updates for all selected machines...\n")
        all_apps = ["None", "None", "None", "None", "None", "None", "None", "None"]
        update_board_records(all_apps, selected_machines, args, "revert.txt")
        exit()
    selected_main_app     = present_list_of_apps(main_apps[-13:])
    selected_solenoid_app = present_list_of_apps(solenoid_apps[-13:])
    selected_pump_app     = present_list_of_apps(pump_apps[-13:])
    selected_nozzle_app   = present_list_of_apps(nozzle_apps[-13:])
    selected_cooling_app  = present_list_of_apps(cooling_apps[-13:])
    selected_qr_app       = present_list_of_apps(qr_apps[-13:])

    all_apps = [selected_main_app, selected_solenoid_app, 
                selected_pump_app, selected_nozzle_app, 
                selected_cooling_app, selected_qr_app]

    clear_screen()
    for i in range(5):
        print_at_top("\033[1m*** SUMMARY OF ALL SELECTION OPTIONS ***\033[0m\n")
        time.sleep(0.3)
        print_at_top("")
        time.sleep(0.2)
    print_at_top("\033[1m*** SUMMARY OF ALL SELECTION OPTIONS ***\033[0m\n")
    print()
    time.sleep(0.5)
    print("\n\033[1mMachines:\033[0m\n")
    for machine in selected_machines:
        print("* " + machine['name'])
    print("\n\n\033[1mFirmware Applications: \033[0m\n")
    print_all_app_details(all_apps)
    time.sleep(2)
    for i in range(7):
        print_at_bottom("\033[1m!!!!!! REVIEW SELECTED OPTIONS CAREFULLY !!!!!!!\033[0m")
        time.sleep(0.4)
        print_at_bottom("")
        time.sleep(0.3)
    print_at_bottom("\033[1m!!!!!! REVIEW SELECTED OPTIONS CAREFULLY !!!!!!!\033[0m")
    time.sleep(1)
    print("\n")
    wait_for_specific_input("yes")
    clear_screen()
    print("\nGenerating report...\n")
    fname = generate_fw_update_report(selected_machines, all_apps)

    update_board_records(all_apps, selected_machines, args, fname)
    print("\n\033[1mDone queuing updates for all boards for selected machines :)\033[0m\n")

#  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  
#  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  

def main():
    global apikey, authtoken
    args = setup_argpase()
    apikey, authtoken = read_key_and_token(args)

    if args.list_all_machines:
        list_all_machines(args)
    if args.list_latest_apps:
        list_latest_apps(args)
    if args.list_logs:
        list_logs(args)
    if args.machine_status:
        get_machine_status(args, None)
    if args.graph_temps:
        graph_temps(args)
    if args.update_fw:
        update_fw(args)

#  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  
#  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  

if __name__ == "__main__":
    main()