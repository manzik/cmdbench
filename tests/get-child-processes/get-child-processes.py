import subprocess
import os
import time

FNULL = open(os.devnull, 'w')
node_process = subprocess.Popen(["node", "deep-child-processes-test.js"], shell=False, stdout=FNULL, stderr=subprocess.STDOUT)
target_pid = node_process.pid
time.sleep(2)
print(target_pid)
subprocess.Popen(['bash', '-c', '. get-children.sh ' + str(target_pid)])