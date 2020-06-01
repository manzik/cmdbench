import time
from collections import namedtuple, defaultdict, deque
import numpy as np
from beeprint import pp
from inspect import isfunction

matplotlib_available = True
try:
    import matplotlib.pyplot as plt
except ImportError:
    matplotlib_available = False


class BenchmarkResults():
    _iterations = []
    def __init__(self, iterations):
        self._iterations = iterations

    def _has_one_iteration(self):
        return len(self._iterations) == 1

    def get_single_iteration(self):
        return BenchmarkDict.from_dict(self._iterations[0])

    def get_iterations(self):
        return BenchmarkDict.from_dict(self._iterations)

    def get_values_per_attribute(self):
        value_per_attribute_dict = self._get_values_per_attribute(self._iterations)
        return BenchmarkDict.from_dict(value_per_attribute_dict)

    # Gets of same-structured objects
    # Returns object of that structure with list of values from those objects
    # Replaces them with replace_func(list_of_objects, key_path) if provided (optional)
    # Example: BenchmarkResults([{"x": 2}, {"x": 3}], None).get_values_per_attribute() == {"x": [2, 3]}
    def _get_values_per_attribute(self, list_of_objects, replace_func = None, key_path = []):
        sample_from_list = list_of_objects[0]
        if(isinstance(sample_from_list, dict)):
            value_per_attribute_dict = {}
            for key, value in sample_from_list.items():
                list_of_objects_from_key = list(map(lambda parent_dict: parent_dict[key], list_of_objects))
                value_per_attribute_dict[key] = self._get_values_per_attribute(list_of_objects_from_key, replace_func, key_path + [key])
            return value_per_attribute_dict
        else:
            values_list = list_of_objects
            if(replace_func is not None and isfunction(replace_func)):
                values_list = replace_func(values_list, key_path)
            return values_list

    def get_statistics(self):

        def stats_replace_func(list_of_objects, key_path):
            sample_data = list_of_objects[0]
            if(isinstance(sample_data, str)):
                return None
            else:
                return BenchmarkStats(list_of_objects)
        
        value_per_attribute_stats_dict = self._get_values_per_attribute(self._iterations, stats_replace_func)
        return BenchmarkDict.from_dict(value_per_attribute_stats_dict)

    def get_averages(self):

        time_series_dict_key = "time_series"

        
        
        def avg_replace_func(list_of_objects, key_path):
            sample_data = list_of_objects[0]
            if(isinstance(sample_data, str)):
                return None
            elif(key_path[0] == time_series_dict_key):
                return list_of_objects
            else:
                return np.hstack(np.array(list_of_objects)).mean()
        
        value_per_attribute_avgs_dict = self._get_values_per_attribute(self._iterations, avg_replace_func)
        
        # Break down time series data to time_series_x_values and time_series_y_values
        averaged_time_series = {}
        # A list of list of x values (in this case, milliseconds) to calculate y averages against
        time_series_x_values = value_per_attribute_avgs_dict["time_series"]["sample_milliseconds"]
        
        # Dict of list of possible y lists for each kind of resource (cpu percentages, memory values)
        time_series_y_values = {}
        
        # Output (updated 1D average) values
        time_series_x_values_out = []
        time_series_y_values_out = {}
        for key, value in  value_per_attribute_avgs_dict["time_series"].items():
            if(key != "sample_milliseconds"):
                time_series_y_values[key] = value
                time_series_y_values_out[key] = []


        # START: Average of the time series algorithm

        time_series_np = np.hstack(np.array(time_series_x_values))
        sample_min_ms = time_series_np.min()
        sample_max_ms = time_series_np.max()
        
        samples_time_avg_max = np.array([np.array(time_series_x).max() for time_series_x in time_series_x_values]).mean()
        samples_time_avg_min = np.array([np.array(time_series_x).min() for time_series_x in time_series_x_values]).mean()
        samples_time_avg = samples_time_avg_max - samples_time_avg_min
        samples_len_avg = np.array([len(time_series_x) for time_series_x in time_series_x_values]).mean()

        # Average milliseconds per sample
        avg_ms_per_sample = samples_time_avg / samples_len_avg

        # Average y values based on each range for x values
        # ranges' length are average milliseconds among x values we have
        time_series_data_count = len(time_series_x_values)
        scanning_time_indexes = [0] * time_series_data_count
        for from_ms in np.arange(sample_min_ms, sample_max_ms, avg_ms_per_sample):
            to_ms = from_ms + avg_ms_per_sample
            
            avging_indexes_list = [[] for _ in range(time_series_data_count)]

            # Find list of indexes for each iteration of benchmarking that match the current
            # range of milliseconds trying to calculate the average for
            for avging_index_ind in range(time_series_data_count):
                target_time_series_x = time_series_x_values[avging_index_ind]
                while(scanning_time_indexes[avging_index_ind] < len(target_time_series_x) and target_time_series_x[scanning_time_indexes[avging_index_ind]] <= to_ms):
                    avging_indexes_list[avging_index_ind].append(scanning_time_indexes[avging_index_ind])
                    scanning_time_indexes[avging_index_ind] += 1

            flattened_indexes = np.hstack(np.array(avging_indexes_list))
            matching_range_indexes_count = len(flattened_indexes)
            no_indexes_for_time_range = matching_range_indexes_count == 0
            if(no_indexes_for_time_range):
                continue
            
            # Calculate average of x values for matching indexes in the range
            avg_x = 0 # i.e. average milliseconds
            for avging_index_ind in range(time_series_data_count):
                avging_indexes = avging_indexes_list[avging_index_ind]
                for avging_index in avging_indexes:
                    avg_x += time_series_x_values[avging_index_ind][avging_index]
            avg_x /= matching_range_indexes_count
            time_series_x_values_out.append(avg_x)

            # Calculate average of y values of each key for matching indexes in the range
            for key_y in time_series_y_values.keys():
                # Y value for this key. Iterates through all keys and changes for each iteration
                avg_key_y = 0
                for avging_index_ind in range(time_series_data_count):
                    avging_indexes = avging_indexes_list[avging_index_ind]
                    for avging_index in avging_indexes:
                        avg_key_y += time_series_y_values[key_y][avging_index_ind][avging_index]
                avg_key_y /= matching_range_indexes_count

                time_series_y_values_out[key_y].append(avg_key_y)

        

        # END: Average of the time series algorithm

        # Pack data from time_series_x_values and time_series_y_values to averaged_time_series
        # and finally time_series data
        averaged_time_series["sample_milliseconds"] = time_series_x_values_out
        for key, value in  time_series_y_values_out.items():
            averaged_time_series[key] = value
        value_per_attribute_avgs_dict["time_series"] = averaged_time_series

        return BenchmarkDict.from_dict(value_per_attribute_avgs_dict)

    def get_resources_plot(self, width = 15, height = 3):
        if(not matplotlib_available):
            raise Exception("You need to install matplotlib before using this method")

        time_series_obj = None
        if(self._has_one_iteration()):
            time_series_obj = self.get_single_iteration()
        else:
            time_series_obj = self.get_averages()
            print(time_series_obj["time_series"])
        
        time_series_obj = time_series_obj["time_series"]

        results_sample_milliseconds = time_series_obj["sample_milliseconds"] # On x axis
        results_memory_values = time_series_obj["memory_bytes"] # On y axis
        results_cpu_percentages = time_series_obj["cpu_percentages"] # On y axis
            

        ## CPU + MEMORY

        # Set the figure's size
        plt.rcParams["figure.figsize"] = (width, height)

        # Data for plotting
        x = results_sample_milliseconds
        memory_y = results_memory_values
        cpu_y = results_cpu_percentages


        color = 'tab:blue'
        fig, ax_memory = plt.subplots()
        ax_memory.grid()
        ax_memory.set_xlabel('Milliseconds')
        ax_memory.set_ylabel('Memory (Bytes)', color=color)
        ax_memory.plot(x, memory_y, color=color, alpha=0.8)
        ax_memory.tick_params(axis='y', labelcolor=color)
        plt.fill_between(x, memory_y, alpha=0.2, color=color)

        color = 'tab:green'
        ax_cpu = ax_memory.twinx()
        ax_cpu.set_ylabel('CPU (%)', color=color)
        ax_cpu.plot(x, cpu_y, color=color, alpha=0.75, linewidth=1)
        ax_cpu.tick_params(axis='y', labelcolor=color)
        #plt.fill_between(x, cpu_y, alpha=0.2, color=color)

        #plt.tight_layout()

        # https://stackoverflow.com/a/31845332
        plt.close(fig)

        return fig

# https://stackoverflow.com/a/41274937
# Allows attribute access through both obj["key"] (internal library convenience) and obj.key (external developer convenience)
class BenchmarkDict(defaultdict):
    def __init__(self):
        super(BenchmarkDict, self).__init__(BenchmarkDict)

    def __getattr__(self, key):
        if key.startswith('_'):
            raise AttributeError(key)
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value

    def __repr__(self):
        return pp(self.to_dict(), False)

    # Converts benchmakr dictionary to a normal dictionary
    def to_dict(self):
        outputDict = {}
        for key, value in self.items():
            attr_dict_pair_value = None
            if(isinstance(value, BenchmarkDict)):
                attr_dict_pair_value = value.to_dict()
            else:
                attr_dict_pair_value = value
            outputDict[key] = attr_dict_pair_value
        return outputDict

    # Iterates through dictionary keys and converts them using get_dict_value_converted recursively 
    @staticmethod
    def from_dict(obj):
        attr_dict = BenchmarkDict()
        for key, value in obj.items():
            attr_dict_pair_value = BenchmarkDict.get_dict_value_converted(value)
            attr_dict.__setattr__(key, attr_dict_pair_value)
        return attr_dict

    # Gets converted value of anything (dict, str, list, etc.) for creation of dictionaries
    @staticmethod
    def get_dict_value_converted(value):
        attr_dict_pair_value = None
        if(isinstance(value, dict)):
            attr_dict_pair_value = BenchmarkDict.from_dict(value)
        elif(isinstance(value, BenchmarkDict)):
            attr_dict_pair_value = BenchmarkDict.from_dict(value)
        elif(isinstance(value, list)):
            newList = []
            for item in value:
                newList.append(BenchmarkDict.get_dict_value_converted(item))
            attr_dict_pair_value = newList
        else:
            attr_dict_pair_value = value
        return attr_dict_pair_value


class BenchmarkStats:
    def __init__(self, data):
        mean_val = sd_val = min_val = max_val = None
        
        # Convert to numpy array and flatten
        data = np.hstack(np.array(data))

        if type(data) is np.ndarray:
            if(len(data) > 0):
                mean_val = np.mean(data)
                sd_val = np.std(data)
                min_val = np.min(data)
                max_val = np.max(data)
        
        self.data = data
        self.mean, self.stdev, self.min, self.max = mean_val, sd_val, min_val, max_val
    def __repr__(self):
        return "(mean: %(mean)s, stdev: %(stdev)s, min: %(min)s, max: %(max)s)" % {
            "mean": self.mean, "stdev": self.stdev,
            "min": self.min, "max": self.max
        }


# https://stackoverflow.com/a/5998359
current_milli_time = lambda: int(round(time.time() * 1000))


def iterable(obj):
    try:
        iter(obj)
    except Exception:
        return False
    else:
        return True


def isfloat(x):
    try:
        val = float(x)
    except ValueError:
        return False
    else:
        return True


def isint(x):
    try:
        val = int(x)
    except ValueError:
        return False
    else:
        return True


# Conversion of time format (hh:mm:ss or mm:ss) to seconds
def get_sec(time_str):
    secs = 0
    time_decimal = 0
    time_decimal_start_ind = time_str.index(".")
    if(time_decimal_start_ind > -1):
        time_decimal = float("0" + time_str[time_decimal_start_ind:])
    time_str = time_str[:time_decimal_start_ind]

    time_tokens = time_str.split(":")
    time_tokens.reverse()
    for token_ind, time_token in enumerate(time_tokens):
        secs += int(time_token) * 60 ** token_ind
    return secs + time_decimal