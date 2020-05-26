import numpy as np
from collections import deque, namedtuple
import sys
import io
import os
import subprocess
import psutil
import time
import sys
import tempfile

# https://stackoverflow.com/a/5998359
current_milli_time = lambda: int(round(time.time() * 1000))

class Benchmark:
    def __init__(self):
        pass

def benchmark_command_avg(command, times):
    benchmarks_results = []
    for _ in range(times):
        benchmarks_result = benchmark_command(command)
        benchmarks_results.append(benchmarks_result)
    
    benchmark_average_results = {
        "benchmarks_results": benchmarks_results
    }

    return benchmark_average_results

Stats = namedtuple("Stats", "mean std")
def np_array_stats(np_arr):
    return Stats(np.mean(np_arr), np.std(np_arr))

def benchmark_command(command):
    commands_list = command.split(" ")

    time_tmp_output_file = tempfile.mkstemp(suffix = '.temp')[1] # [1] for getting filename and not the file's stream

    # Wrap the target command around the time command
    commands_list = ["/usr/bin/time", "-o", time_tmp_output_file, "-v"] + commands_list
    
    time_process = psutil.Popen(commands_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # p is the target process to monitor
    p = None
    # Wait for time to load the target process, then proceed
    while(p is None):
        time_children = time_process.children(recursive=False)
        if(len(time_children) > 0):
            p = time_children[0]

    execution_start = current_milli_time()

    cpu_total_time = 0
    cpu_percentages = deque()

    memory_max = 0
    memory_values = deque()

    disk_io_counters = {}

    process_output_lines = deque()
    process_error_lines = deque()

    while(True):

        time_process_retcode = time_process.poll()
        # retcode would be None while subprocess is running
        if(time_process_retcode is not None or not p.is_running()):
            break
        
        # https://psutil.readthedocs.io/en/latest/#psutil.Process.oneshot
        with p.oneshot():
            try:
                ## CPU
    
                cpu_times = p.cpu_times()
                # https://psutil.readthedocs.io/en/latest/#psutil.Process.cpu_times
                cpu_time = cpu_times.user + cpu_times.system + cpu_times.children_user + cpu_times.children_system + cpu_times.iowait
                cpu_total_time = cpu_time
                
                cpu_percentage = p.cpu_percent()
    
                ## DISK
    
                disk_io_counters = p.io_counters()
    
                ## MEMORY
    
                # http://grodola.blogspot.com/2016/02/psutil-4-real-process-memory-and-environ.html
                
                memory_usage_info = p.memory_info()
                memory_usage = memory_usage_info.rss
                
    
                for child in p.children(recursive=True):
                    child_memory_usage_info = child.memory_info()
                    memory_usage += child_memory_usage_info.rss
                    cpu_percentage += child.cpu_percent()
                
                memory_values.append(memory_usage)
                memory_max = max(memory_max, memory_usage)
                cpu_percentages.append(cpu_percentage)
            except Exception as e:
                # The process might end while we are measuring resources
                print(e)
                break
        
    exection_end = current_milli_time()

    process_output_lines = list(map(lambda line: line.decode(sys.stdout.encoding), time_process.stdout.readlines()))
    process_error_lines = list(map(lambda line: line.decode(sys.stderr.encoding), time_process.stderr.readlines()))

    f = open(time_tmp_output_file, "r")
    gnu_times_lines = list(map(lambda line: line.strip(), f.readlines()))
    gnu_times_dict = {}
    for gnu_times_line in gnu_times_lines:
        tokens = list(map(lambda token: token.strip(), gnu_times_line.rsplit(":", 1)))
        key = tokens[0]
        value = tokens[1]
        gnu_times_dict[key] = value
    f.close()
    os.remove(time_tmp_output_file)
    
    cpu_percentages = np.array(cpu_percentages)
    memory_values = np.array(memory_values)

    resource_usages = {
        "cpu": 
        {
            "total_time": cpu_total_time,
            "percentages": cpu_percentages,
            "percentages_stats": np_array_stats(cpu_percentages)
        },
        "memory": 
        {
            "max": memory_max,
            "values": memory_values,
            "values_stats": np_array_stats(memory_values)
        },
        "disk": 
        {
            "io_counters": disk_io_counters
        },
        "process":
        {
            "stdout_data": "\n".join(process_output_lines),
            "stderr_data": "\n".join(process_error_lines),
            "execution_time": exection_end - execution_start
        },
        "gnu_time_results": gnu_times_dict
    }
    
    return resource_usages