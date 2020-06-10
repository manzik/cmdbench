from .utils import *
from .result import *
from collections import deque
import multiprocessing
import threading
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
is_macos = _platform == "darwin"
is_unix = is_linux or is_macos
is_win = os.name == 'nt'

def benchmark_command(command, iterations_num = 1, raw_data = False):
    if(iterations_num <= 0):
        raise Exception("The number of iterations to run the command should be >= 1")

    raw_benchmark_results = []
    for _ in range(iterations_num):
        raw_benchmark_result = single_benchmark_command_raw(command)
        raw_benchmark_results.append(raw_benchmark_result)
    
    final_benchmark_results = list(map(lambda raw_benchmark_result: raw_benchmark_result if raw_data else raw_to_final_benchmark(raw_benchmark_result), raw_benchmark_results))

    return BenchmarkResults(final_benchmark_results)

def benchmark_command_generator(command, iterations_num = 1, raw_data = False):
    if(iterations_num <= 0):
        raise Exception("The number of iterations to run the command should be >= 1")

    for _ in range(iterations_num):
        raw_benchmark_result = single_benchmark_command_raw(command)
        final_benchmark_result = raw_benchmark_result if raw_data else raw_to_final_benchmark(raw_benchmark_result)
        yield BenchmarkResults([final_benchmark_result])

# Uses benchmark_command_raw and raw_to_final_benchmark to get, compile and format 
# the most accurate info from /user/bin/time and psutil library 
# 
# For reasoning of choosing the right tool (either GNU time or psutil) for each
# resource (CPU, memory and disk usage) refer to the ipython notebook in the repository

def raw_to_final_benchmark(benchmark_raw_dict):

    process_stdout_data = benchmark_raw_dict["general"]["stdout_data"]
    process_stderr_data = benchmark_raw_dict["general"]["stderr_data"]
    process_execution_time = benchmark_raw_dict["gnu_time"]["process"]["execution_time"] if is_linux else benchmark_raw_dict["psutil"]["process"]["execution_time"]

    cpu_user_time = benchmark_raw_dict["psutil"]["cpu"]["user_time"]
    cpu_system_time = benchmark_raw_dict["psutil"]["cpu"]["system_time"]
    cpu_total_time = cpu_user_time + cpu_system_time

    memory_max = benchmark_raw_dict["psutil"]["memory"]["max"]
    memory_max_perprocess = benchmark_raw_dict["psutil"]["memory"]["max_perprocess"]

    time_series_sample_milliseconds = benchmark_raw_dict["time_series"]["sample_milliseconds"]
    time_series_cpu_percentages = benchmark_raw_dict["time_series"]["cpu_percentages"]
    time_series_memory_bytes = benchmark_raw_dict["time_series"]["memory_bytes"]

    exit_code = benchmark_raw_dict["general"]["exit_code"]



    benchmark_results = {
        "process": { "stdout_data": process_stdout_data, "stderr_data": process_stderr_data, "execution_time": process_execution_time, "exit_code": exit_code },
        "cpu": { "user_time": cpu_user_time, "system_time": cpu_system_time, "total_time": cpu_total_time },
        "memory": { "max": memory_max, "max_perprocess": memory_max_perprocess },
        "time_series":
        {
            "sample_milliseconds": time_series_sample_milliseconds,
            "cpu_percentages": time_series_cpu_percentages,
            "memory_bytes": time_series_memory_bytes
        }
    }
    # psutil io_counters() is not available on macos
    if not is_macos:
        disk_read_bytes = benchmark_raw_dict["psutil"]["disk"]["io_counters"]["read_bytes"]
        disk_write_bytes = benchmark_raw_dict["psutil"]["disk"]["io_counters"]["write_bytes"]
        disk_total_bytes = disk_read_bytes + disk_write_bytes

        # Only available on linux
        if(is_linux):
            disk_read_chars = benchmark_raw_dict["psutil"]["disk"]["io_counters"]["read_chars"]
            disk_write_chars = benchmark_raw_dict["psutil"]["disk"]["io_counters"]["write_chars"]
            disk_total_chars = disk_read_chars + disk_write_chars

        # Only available on linux
        if is_win:
            disk_other_count = benchmark_raw_dict["psutil"]["disk"]["io_counters"]["other_count"]
            disk_other_bytes = benchmark_raw_dict["psutil"]["disk"]["io_counters"]["other_bytes"]

        disk_read_count = benchmark_raw_dict["psutil"]["disk"]["io_counters"]["read_count"]
        disk_write_count = benchmark_raw_dict["psutil"]["disk"]["io_counters"]["write_count"]
        disk_total_count = disk_read_count + disk_write_count

        disk_results = {
        "read_bytes": disk_read_bytes,
        "write_bytes": disk_write_bytes,
        "total_bytes": disk_total_bytes
        }

        if is_linux:
            disk_results["read_chars"] = disk_read_chars
            disk_results["write_chars"] = disk_write_chars
            disk_results["total_chars"] = disk_total_chars
        
        if is_win:
            # Count is not really useful
            # disk_results["other_count"] = disk_other_count
            disk_results["other_bytes"] = disk_other_bytes

        benchmark_results["disk"] = disk_results

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
    process_output_lines, process_error_lines = [], []

    # Time series data
    # We don't need fast read access, we need fast insertion so we use deque
    sample_milliseconds, cpu_percentages, memory_values = deque([]), deque([]), deque([])
    
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
    try:
        time_series_dict = manager.dict(time_series_dict_template)
    except Exception as e:
        pass

    # Subprocess: For time series measurements

    # We need a non-blocking method to capture essential info (disk usage, cpu times)
    # and non-essential time-series info in parallel.
    # So we use either multiprocessing or threading to achieve this

    # Linux: Processes are faster than threads
    # Windows: Both are as fast but processes take longer to start
    if is_unix:
        time_series_exec = multiprocessing.Process(target=collect_time_series, args=(time_series_dict, ))
    else:
        time_series_exec = threading.Thread(target=collect_time_series, args=(time_series_dict, ))
    time_series_exec.start()

    # p is always the target process to monitor
    p = None

    # END: Initialization

    # Finally, run the command
    # Master process could be GNU Time running target command or the target command itself
    master_process = psutil.Popen(commands_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    execution_start = current_milli_time()
    
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

    time_series_dict["execution_start"] = execution_start

    if not time_series_dict["skip_benchmarking"]:
        time_series_dict["target_process_pid"] = p.pid
    
    # If we were able to access the process info at least once without access denied error
    had_permission = False

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

                if not is_macos:
                    disk_io_counters = p.io_counters()

                had_permission = True
                
            except psutil.AccessDenied as access_denied_error:
                if is_linux:
                    # On linux, we might get access denied simply because the process has ended
                    # and the io file for that process doesn't exist anymore or is about to be deleted 
                    # by the system and psutil tries to access that. We determine if we are safe by checking if
                    # we were able to acccess pro process io file before or not.
                    # It is an actual access denied error if we were not able to have access before.
                    
                    # os.path.exists and shell checks for pid existence all caused false positives and negatives

                    if had_permission:
                        continue
                    
                print("Access Denied. Root access is needed for monitoring the target command.")
                raise access_denied_error
                break
            except psutil.NoSuchProcess as e:
                # The process might end while we are measuring resources
                # Then we didn't capture the final return code in the while loop, do it now
                master_process_retcode = master_process.poll()
                pass
            except Exception as e:
                raise e
                break
    exection_end = current_milli_time()
    time_series_exec.join()

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

    psutil_read_bytes, psutil_write_bytes = 0, 0
    psutil_read_count, psutil_write_count = 0, 0
    psutil_read_chars, psutil_write_chars = 0, 0

    if(disk_io_counters is not None):
        psutil_read_bytes = disk_io_counters.read_bytes
        psutil_write_bytes = disk_io_counters.write_bytes
        psutil_read_count = disk_io_counters.read_count
        psutil_write_count = disk_io_counters.write_count
        if is_linux:
            psutil_read_chars = disk_io_counters.read_chars
            psutil_write_chars = disk_io_counters.write_chars
        if is_win:
            psutil_other_count = disk_io_counters.other_count
            psutil_other_bytes = disk_io_counters.other_bytes

    # Decode and join all of the lines to a single string for stdout and stderr
    process_output_lines = list(map(lambda line: line.decode(sys.stdout.encoding), master_process.stdout.readlines()))
    process_error_lines = list(map(lambda line: line.decode(sys.stderr.encoding), master_process.stderr.readlines()))
    
    # We're done with the process. Get return code and.
    master_process.communicate()

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
            "process":
            {
                "execution_time": (exection_end - execution_start) / 1000 # milliseconds to seconds
            }
        },
        "general": # Info independent from GNU Time and psutil
        {
            "stdout_data": "\n".join(process_output_lines),
            "stderr_data": "\n".join(process_error_lines),
            "exit_code": gnu_times_dict["Exit status"] if is_linux else master_process.returncode
        },
        "time_series":
        {
            "sample_milliseconds": np.array(sample_milliseconds),
            "cpu_percentages": np.array(cpu_percentages),
            "memory_bytes": np.array(memory_values)
        },
        
    }

    if not is_macos:
        io_counters = {
                    "read_bytes": psutil_read_bytes,
                    "write_bytes": psutil_write_bytes,
                    "read_count": psutil_read_count,
                    "write_count": psutil_write_count
                }

        if is_linux:
            io_counters["read_chars"] = psutil_read_chars
            io_counters["write_chars"] = psutil_write_chars

        if is_win:
            io_counters["other_count"] = psutil_other_count
            io_counters["other_bytes"] = psutil_other_bytes

        resource_usages["psutil"]["disk"] = { "io_counters": io_counters }

    if is_linux:
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
