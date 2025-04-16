import os
import json

# Define the root directory
root_dir = r'C:\Users\gregk\Documents\GitHub\xwa-points\xwing-data2\data\pilots'

# Walk through every file in the directory and subdirectories
for subdir, _, files in os.walk(root_dir):
    for file in files:
        if file.endswith('.json'):
            file_path = os.path.join(subdir, file)
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            modified = False

            # If the file has pilots (it's a ship file), iterate through them
            if isinstance(data, dict) and 'pilots' in data:
                for pilot in data['pilots']:
                    if 'shipAbility' in pilot:
                        ability = pilot['shipAbility']
                        if not ability.get('name') or not ability.get('text'):
                            del pilot['shipAbility']
                            modified = True

            if modified:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                print(f'Updated: {file_path}')
