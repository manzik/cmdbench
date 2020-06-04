from .utils import *
from .result import *
from collections import deque
import multiprocessing
import numpy as np
import sys
import io
import os
import subprocess
import psutil
import sys
import tempfile
import shlex
from sys import platform as _platform

is_linux = _platform.startswith('linux')

def benchmark_command(command, iterations_num = 1, raw_data = False):
    if(iterations_num <= 0):
        raise Exception("The number of iterations to run the command should be >= 1")
    if(iterations_num <= 0):
        raise Exception("The number of times to run the command per each iterations should be >= 1")

    raw_benchmark_results = []
    for _ in range(iterations_num):
        raw_benchmark_result = single_benchmark_command_raw(command)
        raw_benchmark_results.append(raw_benchmark_result)
    
    final_benchmark_results = list(map(lambda raw_benchmark_result: raw_benchmark_result if raw_data else raw_to_final_benchmark(raw_benchmark_result), raw_benchmark_results))

    return BenchmarkResults(final_benchmark_results)

# Uses benchmark_command_raw and raw_to_final_benchmark to get, compile and format 
# the most accurate info from /user/bin/time and psutil library 
#
# For reasoning of choosing the right tool (either GNU time or psutil) for each
# resource (CPU, memory and disk usage) refer to the ipython notebook in the repository

def raw_to_final_benchmark(benchmark_raw_dict):

    process_stdout_data = benchmark_raw_dict["general"]["stdout_data"]
    process_stderr_data = benchmark_raw_dict["general"]["stderr_data"]
    process_execution_time = benchmark_raw_dict["psutil"]["process"]["execution_time"]


    cpu_user_time = benchmark_raw_dict["psutil"]["cpu"]["user_time"]
    cpu_system_time = benchmark_raw_dict["psutil"]["cpu"]["system_time"]
    cpu_total_time = cpu_user_time + cpu_system_time


    memory_max = benchmark_raw_dict["psutil"]["memory"]["max"]
    memory_max_perprocess = benchmark_raw_dict["psutil"]["memory"]["max_perprocess"]


    disk_read_bytes = benchmark_raw_dict["psutil"]["disk"]["io_counters"]["read_bytes"]
    disk_write_bytes = benchmark_raw_dict["psutil"]["disk"]["io_counters"]["write_bytes"]
    disk_total_bytes = disk_read_bytes + disk_write_bytes

    if(is_linux):
        disk_read_chars = benchmark_raw_dict["psutil"]["disk"]["io_counters"]["read_chars"]
        disk_write_chars = benchmark_raw_dict["psutil"]["disk"]["io_counters"]["write_chars"]
        disk_total_chars = disk_read_chars + disk_write_chars

    disk_read_count = benchmark_raw_dict["psutil"]["disk"]["io_counters"]["read_count"]
    disk_write_count = benchmark_raw_dict["psutil"]["disk"]["io_counters"]["write_count"]
    disk_total_count = disk_read_count + disk_write_count


    time_series_sample_milliseconds = benchmark_raw_dict["time_series"]["sample_milliseconds"]
    time_series_cpu_percentages = benchmark_raw_dict["time_series"]["cpu_percentages"]
    time_series_memory_bytes = benchmark_raw_dict["time_series"]["memory_bytes"]

    disk_results = {
        "read_bytes": disk_read_bytes,
        "write_bytes": disk_write_bytes,
        "total_bytes": disk_total_bytes
    }

    if is_linux:
        disk_results["read_chars"] = disk_read_chars
        disk_results["write_chars"] = disk_write_chars
        disk_results["total_chars"] = disk_total_chars

    benchmark_results = {
        "process": { "stdout_data": process_stdout_data, "stderr_data": process_stderr_data, "execution_time": process_execution_time },
        "cpu": { "user_time": cpu_user_time, "system_time": cpu_system_time, "total_time": cpu_total_time },
        "memory": { "max": memory_max, "max_perprocess": memory_max_perprocess },
        "disk": disk_results,
        "time_series":
        {
            "sample_milliseconds": time_series_sample_milliseconds,
            "cpu_percentages": time_series_cpu_percentages,
            "memory_bytes": time_series_memory_bytes
        }
    }

    return benchmark_results

def collect_time_series(time_series_dict):
    
    while(time_series_dict["target_process_pid"] == -1):
        if(time_series_dict["skip_benchmarking"]):
            return

    p = psutil.Process(time_series_dict["target_process_pid"])
    execution_start = time_series_dict["execution_start"]
    sample_milliseconds = time_series_dict["sample_milliseconds"]
    cpu_percentages = time_series_dict["cpu_percentages"]
    memory_values = time_series_dict["memory_values"]

    memory_perprocess_max = 0; time_series_dict["memory_perprocess_max"]
    memory_max = 0

    # Children that we are processing
    # Set for faster "in" operation
    monitoring_process_children_set = set()
    # List for actual process access
    monitoring_process_children = []

    while(True):
        # retcode would be None while subprocess is running
        if(not p.is_running()):
            break
        
        try:
            time_from_monitoring_start = current_milli_time() - execution_start

            cpu_percentage = p.cpu_percent()

            # http://grodola.blogspot.com/2016/02/psutil-4-real-process-memory-and-environ.html
            memory_usage_info = p.memory_info()
            memory_usage = memory_usage_info.rss
            memory_perprocess_max = max(memory_perprocess_max, memory_usage)

            current_children = p.children(recursive=True)
            for child in current_children:
                with child.oneshot():
                    child_memory_usage_info = child.memory_info()
                    child_memory_usage = child_memory_usage_info.rss

                    memory_usage += child_memory_usage

                    memory_perprocess_max = max(memory_perprocess_max, child_memory_usage)
                    # We need to get cpu_percentage() only for children existing for at list one iteration
                    # Calculate CPU usage for children we have been monitoring
                if(child in monitoring_process_children_set):
                    child_cpu_usage = monitoring_process_children[monitoring_process_children.index(child)].cpu_percent()
                    cpu_percentage += child_cpu_usage
                # Add children not already in our monitoring_process_children
                else:
                    monitoring_process_children_set.add(child)
                    monitoring_process_children.append(child)

            memory_max = max(memory_max, memory_usage)

            sample_milliseconds.append(time_from_monitoring_start)
            cpu_percentages.append(cpu_percentage)
            memory_values.append(memory_usage)

        except psutil.AccessDenied as access_denied_error:
            print("Root access is needed for monitoring the target command.")
            raise access_denied_error
            break
        except psutil.NoSuchProcess as e:
            # The process might end while we are measuring resources
            pass
        except Exception as e:
            raise e
            break

    time_series_dict["memory_max"] = memory_max
    time_series_dict["memory_perprocess_max"] = memory_perprocess_max

    time_series_dict["sample_milliseconds"] = sample_milliseconds
    time_series_dict["cpu_percentages"] = cpu_percentages
    time_series_dict["memory_values"] = memory_values 

# Performs benchmarking on the command based on both /usr/bin/time and psutil library
def single_benchmark_command_raw(command):
    # https://docs.python.org/3/library/shlex.html#shlex.split
    commands_list = shlex.split(command)

    time_tmp_output_file = None

    if is_linux:
        # Preprocessing: Wrap the target command around the GNU Time command
        time_tmp_output_file = tempfile.mkstemp(suffix = '.temp')[1] # [1] for getting temporary filename and not the file's stream
        commands_list = ["/usr/bin/time", "-o", time_tmp_output_file, "-v"] + commands_list

    # START: Initialization

    # CPU
    cpu_times = None
    
    # Disk
    disk_io_counters = None

    # Program outputs
    process_output_lines = []
    process_error_lines = []

    # Time series data
    # We don't need fast read access, we need fast insertion so we use deque
    sample_milliseconds = deque([])
    cpu_percentages = deque([])
    memory_values = deque([])

    # END: Initialization

    # Subprocess: For time series measurements
    manager = multiprocessing.Manager()
    time_series_dict_template = {
        "target_process_pid": -1,
        "execution_start": -1, 
        "sample_milliseconds": sample_milliseconds, 
        "cpu_percentages": cpu_percentages, 
        "memory_values": memory_values,
        "memory_max": 0,
        "memory_perprocess_max": 0,
        "skip_benchmarking": False
    }
    time_series_dict = manager.dict(time_series_dict_template)
    time_series_process = multiprocessing.Process(target=collect_time_series, args=(time_series_dict, ))
    time_series_process.start()

    # p is always the target process to monitor
    p = None

    # Finally, run the command
    # Master process could be GNU Time running target command or the target command itself
    master_process = psutil.Popen(commands_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Only in linux, we target command will be GNU Time's child process
    # On other platforms, the main process will be the target process itself
    if not is_linux:
        p = master_process

    # If we are using GNU Time and are on linux:
    # Wait for time to load the target process, then proceed
    # Depending on whether we are on linux or not
    while(p is None and not time_series_dict["skip_benchmarking"]):

        master_process_retcode = master_process.poll()
        if(master_process_retcode != None or not master_process.is_running()):
            time_series_dict["skip_benchmarking"] = True
            break

        time_children = master_process.children(recursive=False)
        if(len(time_children) > 0):
            p = time_children[0]

    execution_start = current_milli_time()
    time_series_dict["execution_start"] = execution_start

    if not time_series_dict["skip_benchmarking"]:
        time_series_dict["target_process_pid"] = p.pid
    
    # While loop runs as long as the target command is running
    master_process_retcode = None
    while(True and not time_series_dict["skip_benchmarking"]):
        master_process_retcode = master_process.poll()
        # retcode would be None while subprocess is running
        if(master_process_retcode is not None or not p.is_running()):
            break
        
        # https://psutil.readthedocs.io/en/latest/#psutil.Process.oneshot
        with p.oneshot():
            try:

                ## CPU
                cpu_times = p.cpu_times()
                
                ## DISK

                disk_io_counters = p.io_counters()

                
            except psutil.AccessDenied as access_denied_error:
                print("Root access is needed for monitoring the target command.")
                raise access_denied_error
                break
            except psutil.NoSuchProcess as e:
                # The process might end while we are measuring resources
                pass
            except Exception as e:
                raise e
                break
    time_series_process.join()
        
    exection_end = current_milli_time()

    memory_max = time_series_dict["memory_max"]
    memory_perprocess_max = time_series_dict["memory_perprocess_max"]
    
    sample_milliseconds = time_series_dict["sample_milliseconds"]
    cpu_percentages = time_series_dict["cpu_percentages"]
    memory_values = time_series_dict["memory_values"]

    cpu_user_time = 0
    cpu_system_time = 0

    if(cpu_times is not None):
        # https://psutil.readthedocs.io/en/latest/#psutil.Process.cpu_times
        cpu_user_time = cpu_times.user + cpu_times.children_user
        cpu_system_time = cpu_times.system + cpu_times.children_system
    
    cpu_total_time = cpu_user_time + cpu_system_time

    psutil_read_bytes = 0
    psutil_write_bytes = 0
    psutil_read_count = 0
    psutil_write_count = 0
    psutil_read_chars = 0
    psutil_write_chars = 0

    if(disk_io_counters is not None):
        psutil_read_bytes = disk_io_counters.read_bytes
        psutil_write_bytes = disk_io_counters.write_bytes
        psutil_read_count = disk_io_counters.read_count
        psutil_write_count = disk_io_counters.write_count
        if(is_linux):
            psutil_read_chars = disk_io_counters.read_chars
            psutil_write_chars = disk_io_counters.write_chars

    # Decode and join all of the lines to a single string for stdout and stderr
    process_output_lines = list(map(lambda line: line.decode(sys.stdout.encoding), master_process.stdout.readlines()))
    process_error_lines = list(map(lambda line: line.decode(sys.stderr.encoding), master_process.stderr.readlines()))

    # Convert deques to numpy array
    sample_milliseconds = np.array(sample_milliseconds)
    cpu_percentages = np.array(cpu_percentages)
    memory_values = np.array(memory_values)

    if(is_linux):
        # Read GNU Time command's output and parse it into a python dictionary
        f = open(time_tmp_output_file, "r")
        gnu_times_lines = list(map(lambda line: line.strip(), f.readlines()))
        gnu_times_dict = {}
        for gnu_times_line in gnu_times_lines:
            tokens = list(map(lambda token: token.strip(), gnu_times_line.rsplit(": ", 1)))
            if(len(tokens) < 2):
                continue
            key = tokens[0]
            value = tokens[1].replace("?", "0")
            gnu_times_dict[key] = value

        # We need a conversion for elapsed time from time format to seconds
        gnu_time_elapsed_wall_clock_key = "Elapsed (wall clock) time (h:mm:ss or m:ss)"
        gnu_times_dict[gnu_time_elapsed_wall_clock_key] = str(get_sec(gnu_times_dict[gnu_time_elapsed_wall_clock_key]))
        # And another conversion for cpu utilization percentage string
        gnu_time_job_cpu_percent = "Percent of CPU this job got"
        gnu_times_dict[gnu_time_job_cpu_percent] = float(gnu_times_dict[gnu_time_job_cpu_percent].replace("%", ""))

        f.close()
        os.remove(time_tmp_output_file)

        # Convert all gnu time output's int values to int and float values to float
        for key, value in gnu_times_dict.items():
            if(isint(value)):
                gnu_times_dict[key] = int(value)
            elif(isfloat(value)):
                gnu_times_dict[key] = float(value)
    
    # GNU Time output: For reference
    
    # {
    #   'Average resident set size (kbytes)': 0,
    #   'Average shared text size (kbytes)': 0,
    #   'Average stack size (kbytes)': 0,
    #   'Average total size (kbytes)': 0,
    #   'Average unshared data size (kbytes)': 0,
    #   'Command being timed': '"node --expose-gc test.js"',
    #   'Elapsed (wall clock) time (h:mm:ss or m:ss)': 5.74,
    #   'Exit status': 0,
    #   'File system inputs': 0,
    #   'File system outputs': 10240,
    #   'Involuntary context switches': 91,
    #   'Major (requiring I/O) page faults': 0,
    #   'Maximum resident set size (kbytes)': 614304,
    #   'Minor (reclaiming a frame) page faults': 740886,
    #   'Page size (bytes)': 4096,
    #   'Percent of CPU this job got': 178,
    #   'Signals delivered': 0,
    #   'Socket messages received': 0,
    #   'Socket messages sent': 0,
    #   'Swaps': 0,
    #   'System time (seconds)': 0.76,
    #   'User time (seconds)': 9.47,
    #   'Voluntary context switches': 7585,
    # }
    
    io_counters = {
                    "read_bytes": psutil_read_bytes,
                    "write_bytes": psutil_write_bytes,
                    "read_count": psutil_read_count,
                    "write_count": psutil_write_count
                }

    if(is_linux):
        io_counters["read_chars"] = psutil_read_chars
        io_counters["write_chars"] = psutil_write_chars

    resource_usages = {
        "psutil": # Data collected from psutil
        {
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
                "io_counters": io_counters
            },
            "process":
            {
                "execution_time": (exection_end - execution_start) / 1000 # milliseconds to seconds
            }
        },
        "general": # Info independent from GNU Time and psutil
        {
            "stdout_data": "\n".join(process_output_lines),
            "stderr_data": "\n".join(process_error_lines),
            "exit_code": gnu_times_dict["Exit status"] if is_linux else master_process_retcode
        },
        "time_series":
        {
            "sample_milliseconds": np.array(sample_milliseconds),
            "cpu_percentages": np.array(cpu_percentages),
            "memory_bytes": np.array(memory_values)
        },
        
    }

    if(is_linux):
        resource_usages["gnu_time"] = {
            "cpu": 
            {
                "user_time": gnu_times_dict["User time (seconds)"],
                "system_time": gnu_times_dict["System time (seconds)"],
                "total_time": gnu_times_dict["User time (seconds)"] + gnu_times_dict["System time (seconds)"]
            },
            "memory": 
            {
                "max_perprocess": gnu_times_dict["Maximum resident set size (kbytes)"] * 1024,
            },
            "disk": 
            {
                # https://stackoverflow.com/a/42127533
                "file_system_inputs": gnu_times_dict["File system inputs"] * 512,
                "file_system_outputs": gnu_times_dict["File system outputs"] * 512
            },
            "process":
            {
                "execution_time": gnu_times_dict["Elapsed (wall clock) time (h:mm:ss or m:ss)"] # milliseconds to seconds
            }
        }
        resource_usages["gnu_time_results"] = gnu_times_dict
    
    return resource_usages