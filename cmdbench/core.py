from .utils import *
from collections import deque
import numpy as np
import sys
import io
import os
import subprocess
import psutil
import sys
import tempfile
import shlex

def benchmark_command(command, iterations_num = 1, debugging = False):
    if(iterations_num <= 0):
        raise Exception("The number of iterations to run the command should be >= 1")
    if(iterations_num <= 0):
        raise Exception("The number of times to run the command per each iterations should be >= 1")

    raw_benchmark_results = []
    for _ in range(iterations_num):
        raw_benchmark_result = single_benchmark_command_raw(command, debugging)
        raw_benchmark_results.append(raw_benchmark_result)
    
    final_benchmark_results = list(map(raw_to_final_benchmark, raw_benchmark_results))

    return BenchmarkResults(final_benchmark_results)

# Uses benchmark_command_raw and raw_to_final_benchmark to get, compile and format 
# the most accurate info from /user/bin/time and psutil library 
#
# For reasoning of choosing the right tool (either GNU time or psutil) for each
# resource (CPU, memory and disk usage) refer to the ipython notebook in the repository

def raw_to_final_benchmark(benchmark_raw_dict):
    benchmark_results = {
        "cpu":
        {
            "user_time": benchmark_raw_dict["gnu_time_results"]["User time (seconds)"], # TODO
            "user_time_psutil": benchmark_raw_dict["cpu"]["user_time"], # TODO
            "system_time": benchmark_raw_dict["gnu_time_results"]["System time (seconds)"], # TODO
            "system_time_psutil": benchmark_raw_dict["cpu"]["system_time"], # TODO
            "total_time": benchmark_raw_dict["gnu_time_results"]["User time (seconds)"] + benchmark_raw_dict["gnu_time_results"]["System time (seconds)"], # TODO
            "total_time_psutil": benchmark_raw_dict["cpu"]["user_time"] + benchmark_raw_dict["cpu"]["system_time"], # TODO
            "utilization_percentage": benchmark_raw_dict["gnu_time_results"]["Percent of CPU this job got"]
        },
        "memory": 
        {
            "max": benchmark_raw_dict["memory"]["max"], # DONE
            "max_perprocess": benchmark_raw_dict["memory"]["max_perprocess"], # DONE
            "max_perprocess_psutil": benchmark_raw_dict["gnu_time_results"]["Maximum resident set size (kbytes)"] * 1024 # DONE
        },
        "disk": 
        {
            "io_counters": 
            {
                "total": 0, # TODO
                "read": 0, # TODO
                "write": 0 # TODO
            }
        },
        "process":
        {
            "stdout_data": benchmark_raw_dict["process"]["stdout_data"], # DONE
            "stderr_data": benchmark_raw_dict["process"]["stderr_data"], # DONE
            "execution_time": benchmark_raw_dict["gnu_time_results"]["Elapsed (wall clock) time (h:mm:ss or m:ss)"], # DONE
            "execution_time_psutil": benchmark_raw_dict["process"]["execution_time"] # TODO
        },
        "time_series":
        {
            "sample_milliseconds": benchmark_raw_dict["time_series"]["sample_milliseconds"], # DONE
            "cpu_percentages": benchmark_raw_dict["time_series"]["cpu_percentages"], # DONE
            "memory_bytes": benchmark_raw_dict["time_series"]["memory_bytes"] # DONE
        }
    }

    return benchmark_results

# Performs benchmarking on the command based on both /usr/bin/time and psutil library
# Debugging mode = false prevents from making calculations that are not going to be used in benchmark_command command
def single_benchmark_command_raw(command, debugging = False):
    
    # https://docs.python.org/3/library/shlex.html#shlex.split
    commands_list = shlex.split(command)

    time_tmp_output_file = tempfile.mkstemp(suffix = '.temp')[1] # [1] for getting filename and not the file's stream

    # Wrap the target command around the time command
    commands_list = ["/usr/bin/time", "-o", time_tmp_output_file, "-v"] + commands_list
    
    time_process = psutil.Popen(commands_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # START: Initialization

    # CPU
    cpu_times = 0

    # Memory
    memory_max = 0
    memory_perprocess_max = 0

    # Disk
    disk_io_counters = {}

    # Program outputs
    process_output_lines = []
    process_error_lines = []

    # Time series data
    sample_milliseconds = []
    cpu_percentages = []
    memory_values = []

    # Children that we are processing
    monitoring_process_children = set()

    # END: Initialization
    
    # p is the target process to monitor
    p = None
    # Wait for time to load the target process, then proceed
    while(p is None):
        time_children = time_process.children(recursive=False)
        if(len(time_children) > 0):
            p = time_children[0]

    execution_start = current_milli_time()
    while(True):

        time_process_retcode = time_process.poll()
        # retcode would be None while subprocess is running
        if(time_process_retcode is not None or not p.is_running()):
            break
        
        # https://psutil.readthedocs.io/en/latest/#psutil.Process.oneshot
        with p.oneshot():
            time_from_monitoring_start = current_milli_time() - execution_start
            try:
                current_children = set(p.children(recursive=True))
                
                ## CPU

                cpu_percentage = p.cpu_percent()

                # We need to get cpu_percentage() only for children existing for at list one iteration
                # Calculate CPU usage for children we have been monitoring
                for existing_child in monitoring_process_children.union(current_children):
                    cpu_percentage += existing_child.cpu_percent()
                
                # Add children not already in our monitoring_process_children
                for new_child in current_children.difference(monitoring_process_children):
                    monitoring_process_children.add(new_child)

                cpu_percentages.append(cpu_percentage)
    
                # We will be using GNU Time's cpu times in production code and not psutil's
                if(debugging):
                    cpu_times = p.cpu_times()
    
                ## DISK
    
                disk_io_counters = p.io_counters()
    
                ## MEMORY
    
                # http://grodola.blogspot.com/2016/02/psutil-4-real-process-memory-and-environ.html
                
                memory_usage_info = p.memory_info()
                memory_usage = memory_usage_info.rss
                memory_perprocess_max = max(memory_perprocess_max, memory_usage_info.rss)
                
                for child in current_children:
                    child_memory_usage_info = child.memory_info()
                    memory_usage += child_memory_usage_info.rss
                    memory_perprocess_max = max(memory_perprocess_max, child_memory_usage_info.rss)
                    
                
                memory_values.append(memory_usage)
                memory_max = max(memory_max, memory_usage)

                ## ADD SAMPLE'S TIME

                sample_milliseconds.append(time_from_monitoring_start)

            except psutil.AccessDenied as access_denied_error:
                print("Root access is needed for monitoring the target command.")
                raise access_denied_error
                break
            except psutil.NoSuchProcess:
                # The process might end while we are measuring resources
                pass
            except Exception as e:
                raise e
                break
        
    exection_end = current_milli_time()

    # https://psutil.readthedocs.io/en/latest/#psutil.Process.cpu_times
    cpu_user_time = cpu_times.user
    cpu_system_time = cpu_times.system
    cpu_total_time = cpu_user_time + cpu_system_time + cpu_times.children_user + cpu_times.children_system

    # Decode and join all of the lines to a single string for stdout and stderr
    process_output_lines = list(map(lambda line: line.decode(sys.stdout.encoding), time_process.stdout.readlines()))
    process_error_lines = list(map(lambda line: line.decode(sys.stderr.encoding), time_process.stderr.readlines()))

    # Read GNU Time command's output and parse it into a python dictionary
    f = open(time_tmp_output_file, "r")
    gnu_times_lines = list(map(lambda line: line.strip(), f.readlines()))
    gnu_times_dict = {}
    for gnu_times_line in gnu_times_lines:
        tokens = list(map(lambda token: token.strip(), gnu_times_line.rsplit(": ", 1)))
        key = tokens[0]
        value = tokens[1]
        gnu_times_dict[key] = value
    
    # We need a conversion for elapsed time from time format to seconds
    gnu_time_elapsed_wall_clock_key = "Elapsed (wall clock) time (h:mm:ss or m:ss)"
    gnu_times_dict[gnu_time_elapsed_wall_clock_key] = str(get_sec(gnu_times_dict[gnu_time_elapsed_wall_clock_key]))
    # And another conversion for cpu utilization percentage string
    gnu_time_job_cpu_percent = "Percent of CPU this job got"
    gnu_times_dict[gnu_time_job_cpu_percent] = float(gnu_times_dict[gnu_time_job_cpu_percent].replace("%", ""))

    f.close()
    os.remove(time_tmp_output_file)
    
    # Convert deques to numpy array
    sample_milliseconds = np.array(sample_milliseconds)
    cpu_percentages = np.array(cpu_percentages)
    memory_values = np.array(memory_values)

    # Convert all gnu time output's int values to int and float values to float
    for key, value in gnu_times_dict.items():
        if(isint(value)):
            gnu_times_dict[key] = int(value)
        elif(isfloat(value)):
            gnu_times_dict[key] = float(value)

    resource_usages = {
        "cpu": 
        {
            "total_time": cpu_total_time,
            "user_time": cpu_user_time,
            "system_time": cpu_system_time
        },
        "memory": 
        {
            "max": memory_max,
            "max_perprocess": memory_perprocess_max,
        },
        "disk": 
        {
            "io_counters": disk_io_counters
        },
        "process":
        {
            "stdout_data": "\n".join(process_output_lines),
            "stderr_data": "\n".join(process_error_lines),
            "execution_time": (exection_end - execution_start) / 1000 # milliseconds to seconds
        },
        "time_series":
        {
            "sample_milliseconds": sample_milliseconds,
            "cpu_percentages": cpu_percentages,
            "memory_bytes": memory_values
        },
        "gnu_time_results": gnu_times_dict
    }
    
    return resource_usages