import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)

from scripts.jobfile_class import JobFile

yaml_path = sys.argv[1]
job = JobFile(yaml_path)
job.run()
