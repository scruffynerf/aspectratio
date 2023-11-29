import os
import sys
import json

try:
    import stashapi.log as log
    import stashapi.marker_parse as mp
    from stashapi.tools import human_bytes
    from stashapi.stash_types import PhashDistance
    from stashapi.stashapp import StashInterface
except ModuleNotFoundError:
    print("You need to install the stashapp-tools (stashapi) python module. (CLI: pip install stashapp-tools)", file=sys.stderr)

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

def get_ids(obj):
    ids = []
    for item in obj:
        ids.append(item['id'])
    return ids

def get_names(obj):
    names = []
    for item in obj:
        names.append(item['name'])
    return names

def parent_tag(tag_id):
    parenttagname = config.ratio_parent_name
    parent_tag_id = stash.find_tag(parenttagname, create=True).get("id")
    tag_update = {}
    tag_update["id"] = tag_id
    tag_update["parent_ids"] = parent_tag_id
    stash.update_tag(tag_update)
    return

def catchup():
    ratio_names = config.ratiorange.keys()
    parenttagname = config.ratio_parent_name
    parent_tag_id = stash.find_tag(parenttagname, create=True).get("id")
    for tagname in ratio_names:
        tag_id = stash.find_tag(tagname, create=True).get("id")
        parent_tag(tag_id)
    filtertags = {}
    filtertags["value"] = parent_tag_id
    filtertags["depth"] = -1
    filtertags["modifier"] = "EXCLUDES"
    filter = {}
    filter["tags"] = filtertags
    filterlimits = {}
    filterlimits["per_page"] = -1
    found = stash.find_scenes(filter, filterlimits)
    total = len(found)
    for count, scene in enumerate(found):
       result = checkratio(scene)
       log.debug(f"{scene['title']}: {result}")
       log.progress((1+count)/total)

def checkratio(scene):
    existing_tags = get_names(scene["tags"])
    height = scene["file"]["height"]
    width = scene["file"]["width"]
    ratio = round(width/height,2)
    for tagname, range in config.ratiorange.items() :
        if ratio >= range[0] and ratio <=range[1] :
           if tagname not in existing_tags:
              tag_ratio = stash.find_tag(tagname, create=True).get("id")
              parent_tag(tag_ratio)
              stash.update_scenes({
                'ids': [scene['id']],
                'tag_ids': {
                    'mode': 'ADD',
                    'ids': [tag_ratio]
                }
              })
              return(f"{tagname} matched and set")
           return(f"{tagname} matched but already set")
    return(f"Aspect Ratio - no ratio matched this ratio: {ratio}")

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
            catchup() #loops thru all scenes, and tag
        exit_plugin("Aspect Ratio plugin finished")

    try:
        HOOKCONTEXT = json_input['args']["hookContext"]
    except:
        exit_plugin("Aspect Ratio hook: No hook context")

    log.debug("--Starting Hook 'Aspect Ratio'--")

    sceneID = HOOKCONTEXT['id']
    scene = stash.find_scene(sceneID)

    results = checkratio(scene)
    exit_plugin(results)

main()
