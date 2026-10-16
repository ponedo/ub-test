#!/usr/bin/env python3
"""Keep the accepted workload/verifier; use only the corrected local host observer."""
import importlib.util, runpy, os
from pathlib import Path
import sys
here=Path(__file__).resolve().parent
if os.environ.get('BUILD_TOOLS'):sys.path.insert(0,os.environ['BUILD_TOOLS'])
spec=importlib.util.spec_from_file_location('guard',here/'guard.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);sys.modules['guard']=module
runpy.run_path(str(here.parent/'jetty-resource-mapping/harness.py'),run_name='__main__')
