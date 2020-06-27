from inspect import isfunction
import cmdbench
import matplotlib.pyplot as plt

""" 
Command object options:

The parallel function will be used if "is_parallel" is set to true, or "parallel_argfiles" or "parallel_args" is specified.

"is_parallel": Boolean; Forcefully disables or enables the use of parallel function
"command": String; String or a function returning the string function(samples)
"parallel_argfiles": List; Array of files to provide to the parallel function (after :::)
"parallel_args": String; Parameters to use before the command ("parallel [args] <target_command> ::: files")
"""

def get_results_from_benchmarks_list(benchmark_firsts_list):
    return {
        "memory": max(list(map(lambda result: result.memory.max, benchmark_firsts_list))),
        "disk_read": max(list(map(lambda result: result.disk.read_chars, benchmark_firsts_list))),
        "disk_write": max(list(map(lambda result: result.disk.write_chars, benchmark_firsts_list))),
        "runtime": sum(list(map(lambda result: result.process.execution_time, benchmark_firsts_list)))
    }

# Helper method from cmdbench.result

# Gets of same-structured objects
# Returns object of that structure with list of values from those objects
# Replaces them with replace_func(list_of_objects) if provided (optional)
# Example: BenchmarkResults([{"x": 2}, {"x": 3}], None).get_values_per_attribute() == {"x": [2, 3]}
def get_values_per_attribute(list_of_objects, replace_func = None, key_path = []):
        sample_from_list = list_of_objects[0]
        if(isinstance(sample_from_list, dict)):
            value_per_attribute_dict = {}
            for key, value in sample_from_list.items():
                list_of_objects_from_key = list(map(lambda parent_dict: parent_dict[key], list_of_objects))
                value_per_attribute_dict[key] = get_values_per_attribute(list_of_objects_from_key, replace_func, key_path + [key])
            return value_per_attribute_dict
        else:
            values_list = list_of_objects
            if(replace_func is not None and isfunction(replace_func)):
                values_list = replace_func(values_list)
            return values_list
        
def two_dimensional_samples_avg(dicts_2d_list):
    sample_size_avgs_len = len(dicts_2d_list[0])
    sample_size_avgs = []
    
    for sample_index in range(sample_size_avgs_len):
        dicts_list = list(map(lambda lst: lst[sample_index], dicts_2d_list))
        avg_dict = get_values_per_attribute(dicts_list, lambda lst: sum(lst) / len(lst))
        sample_size_avgs.append(avg_dict)
    return sample_size_avgs

def get_last_n_lines(string, n):
    return "\n".join(string.split("\n")[-n:])

def get_command_groups_usage(command_groups, subsamples, reset_func, benchmark_list_to_results):
    
    index_debug_output, query_debug_output = "", ""

    result_dict = {}

    debug_str = ""

    for key in command_groups.keys():
        commands_benchmark_list = []

        benchmarking_commands = command_groups[key]
        for command_dict in benchmarking_commands:
        
            is_parallel = None
            
            if("use_parallel" in command_dict.keys()):
                # Should use use_parallel if is present as user is trying to force parallel's usage state
                is_parallel = command_dict["use_parallel"]
            else:
                # Should use parallel if one of these options are present
                is_parallel = len(list(set(["use_parallel", "parallel_args", "parallel_argfiles"]) & set(command_dict.keys()))) > 0
            
            for command_dict in benchmarking_commands:
                final_benchmarking_command = ""
                              
                # The parallel command and it's options (arguments?)
                if(is_parallel):
                    final_benchmarking_command += "parallel "
                if("parallel_args" in command_dict.keys()):
                    final_benchmarking_command += command_dict["parallel_args"] + " "
                # Command
                if(isfunction(command_dict["command"])):
                    final_benchmarking_command += command_dict["command"](subsamples)
                else:
                    final_benchmarking_command += command_dict["command"]
                
                # Argfiles if is using parallel
                if(is_parallel):
                    final_benchmarking_command += " ::: "
                    if("parallel_argfiles" in command_dict.keys()):
                        final_benchmarking_command += " ".join(command_dict["parallel_argfiles"])
                    else:
                        final_benchmarking_command += " ".join(subsamples)
                
                debug_str += (">>>>>>>>>>>>>") + "\n"
                debug_str += (final_benchmarking_command) + "\n"
                command_result = cmdbench.benchmark_command(final_benchmarking_command).get_first_iteration()
                debug_str += ("STDOUT: " + command_result.process.stdout_data) + "\n"
                debug_str += ("STDERR: " + command_result.process.stderr_data) + "\n"
                debug_str += ("<<<<<<<<<<<<<") + "\n"
                                  
                commands_benchmark_list.append(command_result)
                              
        commands_benchmark_results = benchmark_list_to_results(commands_benchmark_list)

        result_dict[key] = commands_benchmark_results

    return result_dict, debug_str


def multi_cmdbench(command_groups, reset_func, benchmark_list_to_results, iterations, sampling_func, sample_sizes):
    iterations_results = []
    debug_str = ""
    for iteration in range(iterations):
        iteration_results = []
        for sample_size in sample_sizes:
            reset_func()
            subsamples = sampling_func(sample_size)
            sample_results, group_debug_str = get_command_groups_usage(command_groups, subsamples, reset_func, benchmark_list_to_results)
            iteration_results.append(sample_results)
            debug_str += group_debug_str
        iterations_results.append(iteration_results)
    # iterations_results will be 2d array of iterations containing results for each sample size
    return two_dimensional_samples_avg(iterations_results), debug_str

def plot_resources(results_arr, sample_sizes, key):
    results = list(map(lambda result: result[key], results_arr))
    print(results)
    
    memory_usages = list(map(lambda result: result["memory"], results))
    disk_write_usages = list(map(lambda result: result["disk_write"], results))
    disk_read_usages = list(map(lambda result: result["disk_read"], results))
    runtime_usages = list(map(lambda result: result["runtime"], results))
    
    fig, ax = plt.subplots(1, 4)
    
    plt1, plt2, plt3, plt4 = ax
    
    label_descriptions = {
        "o": "Disk write",
        ">": "Disk read",
        "s": "Memory usage",
        "^": "Runtime"
    }
    
    plt1.plot(sample_sizes, disk_write_usages, '-o', color='green', label=label_descriptions['o'])
    plt2.plot(sample_sizes, disk_read_usages, '-o', color='green', label=label_descriptions['o'])
    plt3.plot(sample_sizes, memory_usages, '-s', color='blue', label=label_descriptions['s'])
    plt4.plot(sample_sizes, runtime_usages, '-^', color='red', label=label_descriptions['^'])
    
    # plt.legend(numpoints=1, bbox_to_anchor=(1.04,1), loc="upper left")
    
    plt1.set_xlabel('Sample size', fontsize = 16)
    plt2.set_xlabel('Sample size', fontsize = 16)
    plt3.set_xlabel('Sample size', fontsize = 16)
    plt4.set_xlabel('Sample size', fontsize = 16)
    
    plt1.set_ylabel('Disk write', fontsize = 16)
    plt2.set_ylabel('Disk read', fontsize = 16)
    plt3.set_ylabel('Memory usage', fontsize = 16)
    plt4.set_ylabel('Runtime', fontsize = 16)
    
    plt.suptitle(key, fontsize = 20)