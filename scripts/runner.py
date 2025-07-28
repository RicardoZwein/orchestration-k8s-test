from yaml import safe_load, dump
import json
from color_classes import bcolors

def read_yaml(yaml_file_path):
    REQUIRED_FIELDS = {"job_id", "type", "query", "output"}

    with open(yaml_file_path, 'r') as f:
        file_content = safe_load(f)

    missing = REQUIRED_FIELDS - file_content.keys()
    if missing:
        raise ValueError(f"Missing required fields: {missing} \n \n")

    if "notify" not in file_content:
        print(f"\n{bcolors.WARNING} Notify not found. Defaulting to `false`. Please define it explicitly. {bcolors.ENDC}\n \n")
    
    query = file_content['query']
    output = file_content['output']
    print(f"Query: {query}")
    print(f"Output Path: {output}")

    return {
        "query": query,
        "output_path": output
    }


path = "jobs/weekly-inactive-users.yaml"
read_yaml(path)