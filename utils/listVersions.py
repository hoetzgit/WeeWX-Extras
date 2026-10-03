#!/usr/bin/env python

import subprocess
REPOS_DIR = '/home/richbell/weewx_code/'
WEEWX_DIR = '/home/richbell/weewx'
repos = ['weewx-gw1000',
         'WeeWX-Extras',
         'vds-weewx-v3-mem-extension',
         'weewx-cmon',
         
         'weewx-celestial',
         'weewx-loopdata',
         'weewx-nws',
         'weewx-skyfield',

         'weewx-extensions/aqi-xtype',
         'weewx-extensions/healthchecks',
         'weewx-extensions/jas',
         'weewx-extensions/pushover',

         'weewx-mqtt/plugin-loopdata',
         'weewx-mqtt/publish',
         'weewx-mqtt/replicate',
         'weewx-mqtt/subscribe',

         'configs',
         'secrets']

command = ['git', 'fetch', '--quiet']
print(f'\nRunning command: {" ".join(command)}')
try:
    process = subprocess.Popen(command, stdout=subprocess.PIPE, cwd=WEEWX_DIR)
    output, unused_err = process.communicate()
    print(f'weewx: {output.decode("utf-8")}')
except FileNotFoundError:
    print(f'{WEEWX_DIR} does not exist')

for repo in repos:
    try:
        cwd = f'{REPOS_DIR}{repo}'
        process = subprocess.Popen(command, stdout=subprocess.PIPE, cwd=cwd)
        output, unused_err = process.communicate()
        print(f'{repo}: {output.decode("utf-8")}')
    except FileNotFoundError:
        print(f'{repo} does not exist')

command = ['git', 'status', '--branch', '-uno', '--null']
print(f'\nRunning command: {" ".join(command)}')
try:
    process = subprocess.Popen(command, stdout=subprocess.PIPE, cwd=WEEWX_DIR)
    output, unused_err = process.communicate()
    print(f'weewx: {output.decode("utf-8")}')
except FileNotFoundError:
    print(f'{WEEWX_DIR} does not exist')

for repo in repos:
    try:
        cwd = f'{REPOS_DIR}{repo}'
        process = subprocess.Popen(command, stdout=subprocess.PIPE, cwd=cwd)
        output, unused_err = process.communicate()
        print(f'{repo}: {output.decode("utf-8")}')
    except FileNotFoundError:
        # print(f'{repo} does not exist')
        continue

command = ['git', 'log', '--format=format:"%ci %h %d %s"', '-n 1']
print(f'\nRunning command: {" ".join(command)}')
try:
    process = subprocess.Popen(command, stdout=subprocess.PIPE, cwd=WEEWX_DIR)
    output, unused_err = process.communicate()
    print(f'weewx: {output.decode("utf-8")}')
except FileNotFoundError:
    print(f'{WEEWX_DIR} does not exist')

for repo in repos:
    try:
        cwd = f'{REPOS_DIR}{repo}'
        process = subprocess.Popen(command, stdout=subprocess.PIPE, cwd=cwd)
        output, unused_err = process.communicate()
        print(f'{repo}: {output.decode("utf-8")}')
    except FileNotFoundError:
        # print(f'{repo} does not exist')
        continue

print("\nFor more information run the following commands from the repository directory.")
print('  git log HEAD..origin --format="format:%ci %h %d %s"')
print('  git diff HEAD...origin/master')
