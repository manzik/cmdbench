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
        
        time_series_x = deque([]) # A list of list of x values (in this case, milliseconds) to calculate y averages against
        time_series_y_values = {} # Dict of list of possible y lists for each kind of resource
        def avg_replace_func(list_of_objects, key_path):
            sample_data = list_of_objects[0]
            if(isinstance(sample_data, str)):
                return None
            elif(key_path[0] == time_series_dict_key):
                if(["sample_milliseconds", "exit_code"].index(key_path[1]) > -1):
                    time_series_x.append(list_of_objects)
                else:
                    time_series_y_values[key_path[1]] = list_of_objects
            else:
                return np.hstack(np.array(list_of_objects)).mean()

        averaged_time_series = {}

        # TODO: Implement average of the time series algorithm
        
        value_per_attribute_avgs_dict = self._get_values_per_attribute(self._iterations, avg_replace_func)
        
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

        results_sample_milliseconds = time_series_obj["sample_milliseconds"]

        results_memory_values = time_series_obj["memory_bytes"]
        results_cpu_percentages = time_series_obj["cpu_percentages"]
            

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

    @staticmethod
    def from_dict(obj):
        attr_dict = BenchmarkDict()
        for key, value in obj.items():
            attr_dict_pair_value = BenchmarkDict.get_dict_value_converted(value)
            attr_dict.__setattr__(key, attr_dict_pair_value)
        return attr_dict

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