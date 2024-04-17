#!/usr/bin/env python3
import yaml
import json
from argparse import ArgumentParser

def action_json(args):

    with open('scripts/example_data.json') as json_file:
        print(json.dumps(json.loads(json_file.read()), indent=2))

def action_yaml(args):
    with open('scripts/example_data.yaml') as yaml_file:
        print(yaml.dump(yaml.safe_load(yaml_file.read()), indent=2))

def invalid_action(args):
    print(f'ERROR: Unsupported action: {args.action}')
    exit(1)

def main():

    parser = ArgumentParser(
        prog='DummyProgram',
        description='This program does nothing important',
        epilog='This is the end of the program'
    )
    parser.add_argument('action', help='An action to run: json,yaml')

    args = parser.parse_args()

    {
        'json': action_json,
        'yaml': action_yaml
    }.get(args.action, invalid_action)(args)

if __name__ == '__main__':
    main()
