import os
import sys
import json

try:
    import stashapi.log as log
    from stashapi.stash_types import PhashDistance  # kept for consistency
    from stashapi.stashapp import StashInterface
except ModuleNotFoundError:
    print("You need to install the stashapp-tools (stashapi) python module. (Either from community plugins or by runninng `pip install stashapp-tools` in a CLI)", file=sys.stderr)
    sys.exit(1)

# plugins don't start in the right directory, let's switch to the local directory
os.chdir(os.path.dirname(os.path.realpath(__file__)))

if not os.path.exists("config.py"):
    with open("aspect_ratiodefaults.py", 'r') as default:
        config_lines = default.readlines()
    with open("config.py", 'w') as firstrun:
        firstrun.write("from aspect_ratiodefaults import *\n")
        for line in config_lines:
            if not line.startswith("##"):
                firstrun.write(f"#{line}")

import config

SCENE_FRAGMENT = """
id
title
tags { name }
files {
  width
  height
}
"""

def configfile_edit(configfile, name: str, state: str):
    found = 0
    with open(configfile, 'r') as file:
        config_lines = file.readlines()
    with open(configfile, 'w') as file_w:
        for line in config_lines:
            if name == line.split("=")[0].strip():
                file_w.write(f"{name} = {state}\n")
                found += 1
            elif "#" + name == line.split("=")[0].strip():
                file_w.write(f"{name} = {state}\n")
                found += 1
            else:
                file_w.write(line)
        if not found:
            file_w.write(f"#\n{name} = {state}\n")
            found = 1
    return found

def exit_plugin(msg=None, err=None):
    if msg is None and err is None:
        msg = "plugin ended"
    output_json = {"output": msg, "error": err}
    print(json.dumps(output_json))
    sys.exit()

def get_names(obj):
    names = []
    for item in obj or []:
        names.append(item['name'])
    return names

def parent_tag(tag_id):
    parenttagname = config.ratio_parent_name
    parent_tag_id = stash.find_tag(parenttagname, create=True).get("id")
    tag_update = {"id": tag_id, "parent_ids": [parent_tag_id]}
    stash.update_tag(tag_update)

def catchup():
    ratio_names = list(config.ratiorange.keys())
    parenttagname = config.ratio_parent_name
    parent_tag_id = stash.find_tag(parenttagname, create=True).get("id")
    
    for tagname in ratio_names:
        tag_id = stash.find_tag(tagname, create=True).get("id")
        parent_tag(tag_id)
    
    filtertags = {"value": parent_tag_id, "depth": -1, "modifier": "EXCLUDES"}
    filter = {"tags": filtertags}
    filterlimits = {"per_page": -1}
    
    found = stash.find_scenes(filter, filterlimits, fragment=SCENE_FRAGMENT)
    total = len(found)
    
    for count, scene in enumerate(found):
        result = checkratio(scene)
        log.debug(f"{scene.get('title', 'Untitled')}: {result}")
        log.progress((1 + count) / total)

def checkratio(scene):
    existing_tags = get_names(scene.get("tags"))
    
    files = scene.get("files") or []
    file_data = files[0] if files else scene.get("file") or {}
    
    height = file_data.get("height")
    width = file_data.get("width")
    
    if height is None or width is None:
        return f"Aspect Ratio - missing dimensions for scene {scene.get('id')}"
    
    ratio = round(width / height, 2)
    
    for tagname, range_vals in config.ratiorange.items():
        if range_vals[0] <= ratio <= range_vals[1]:
            if tagname not in existing_tags:
                tag_ratio = stash.find_tag(tagname, create=True).get("id")
                parent_tag(tag_ratio)
                stash.update_scenes({
                    'ids': [scene['id']],
                    'tag_ids': {'mode': 'ADD', 'ids': [tag_ratio]}
                })
                return f"{tagname} matched and set"
            return f"{tagname} matched but already set"
    return f"Aspect Ratio - no ratio matched: {ratio}"

def main():
    global stash
    json_input = json.loads(sys.stdin.read())
    FRAGMENT_SERVER = json_input["server_connection"]
    stash = StashInterface(FRAGMENT_SERVER)
    
    PLUGIN_ARGS = False
    HOOKCONTEXT = False

    try:
        PLUGIN_ARGS = json_input['args']["mode"]
    except:
        pass

    if PLUGIN_ARGS:
        log.debug("--Starting Plugin 'Aspect Ratio'--")
        if "catchup" in PLUGIN_ARGS:
            log.info("Catching up with Aspect Ratio tagging on older files")
            catchup()
        exit_plugin("Aspect Ratio plugin finished")

    try:
        HOOKCONTEXT = json_input['args']["hookContext"]
    except:
        exit_plugin("Aspect Ratio hook: No hook context")

    log.debug("--Starting Hook 'Aspect Ratio'--")

    sceneID = HOOKCONTEXT['id']
    scene = stash.find_scene(sceneID, fragment=SCENE_FRAGMENT)

    results = checkratio(scene)
    exit_plugin(results)

main()
