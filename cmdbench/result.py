from .utils import *
from inspect import isfunction
from scipy.interpolate import interp1d
import math

matplotlib_available = True
try:
    import matplotlib.pyplot as plt
except ImportError:
    matplotlib_available = False

class BenchmarkResults():
    iterations = []
    def __init__(self, iterations = []):
        self.iterations = iterations

    def _has_one_iteration(self):
        return len(self.iterations) == 1

    def add_benchmark_result(self, benchmark_result):
        self.iterations += benchmark_result.iterations

    def get_first_iteration(self):
        return BenchmarkDict.from_dict(self.iterations[0])

    def get_iterations(self):
        return BenchmarkDict.from_dict(self.iterations)

    def get_values_per_attribute(self):
        value_per_attribute_dict = self._get_values_per_attribute(self.iterations)
        return BenchmarkDict.from_dict(value_per_attribute_dict)

    # Gets of same-structured objects
    # Returns object of that structure with list of values from those objects
    # Replaces them with replace_func(list_of_objects, key_path) if provided (optional)
    # Example: BenchmarkResults([{"x": 2}, {"x": 3}], None).get_values_per_attribute() == {"x": [2, 3]}
    def _get_values_per_attribute(self, list_of_objects, replace_func = None, key_path = []):
        sample_from_list = list_of_objects[0]
        if isinstance(sample_from_list, dict):
            value_per_attribute_dict = {}
            for key, value in sample_from_list.items():
                list_of_objects_from_key = list(map(lambda parent_dict: parent_dict[key], list_of_objects))
                value_per_attribute_dict[key] = self._get_values_per_attribute(list_of_objects_from_key, replace_func, key_path + [key])
            return value_per_attribute_dict
        else:
            values_list = list_of_objects
            if replace_func is not None and isfunction(replace_func):
                values_list = replace_func(values_list, key_path)
            return values_list

    def get_statistics(self):

        def stats_replace_func(list_of_objects, key_path):
            sample_data = list_of_objects[0]
            if isinstance(sample_data, str):
                return None
            else:
                return BenchmarkStats(list_of_objects)
        
        value_per_attribute_stats_dict = self._get_values_per_attribute(self.iterations, stats_replace_func)
        return BenchmarkDict.from_dict(value_per_attribute_stats_dict)

    def get_averages(self):
        time_series_dict_key = "time_series"

        def avg_replace_func(list_of_objects, key_path):
            sample_data = list_of_objects[0]
            if isinstance(sample_data, str):
                return None
            elif key_path[0] == time_series_dict_key:
                return list_of_objects
            else:
                return np.mean(list_of_objects)
        
        value_per_attribute_avgs_dict = self._get_values_per_attribute(self.iterations, avg_replace_func)
        
        # Break down time series data to time_series_x_values and time_series_y_values
        averaged_time_series = {}
        time_series_x_values = value_per_attribute_avgs_dict["time_series"]["sample_milliseconds"]
        time_series_y_values = {}

        for key, value in value_per_attribute_avgs_dict["time_series"].items():
            if key != "sample_milliseconds":
                time_series_y_values[key] = value

        # Use the min and max values of time to create a uniform grid
        min_time = max([min(ts) for ts in time_series_x_values])
        max_time = min([max(ts) for ts in time_series_x_values])
        
        # Define a common time grid (uniform x values)
        uniform_time_grid = np.linspace(min_time, max_time, num=500)
        
        time_series_y_values_out = {key: np.zeros_like(uniform_time_grid) for key in time_series_y_values}

        # Iterate over each time series and interpolate it on the uniform grid
        for i in range(len(time_series_x_values)):
            x_vals = time_series_x_values[i]
            
            for key in time_series_y_values.keys():
                y_vals = time_series_y_values[key][i]
                f_interp = interp1d(x_vals, y_vals, bounds_error=False, fill_value="extrapolate")
                interpolated_y = f_interp(uniform_time_grid)
                time_series_y_values_out[key] += interpolated_y

        # Compute the average by dividing by the number of time series
        for key in time_series_y_values_out.keys():
            time_series_y_values_out[key] /= len(time_series_x_values)

        # Pack data into averaged_time_series
        averaged_time_series["sample_milliseconds"] = uniform_time_grid
        for key, value in time_series_y_values_out.items():
            averaged_time_series[key] = value

        value_per_attribute_avgs_dict["time_series"] = averaged_time_series

        return BenchmarkDict.from_dict(value_per_attribute_avgs_dict)


    def get_resources_plot(self, width = 15, height = 3):
        if not matplotlib_available:
            raise Exception("You need to install matplotlib before using this method")

        time_series_obj = None
        if self._has_one_iteration():
            time_series_obj = self.get_first_iteration()
        else:
            time_series_obj = self.get_averages()
        
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

        # START: Rescale memory_y data to proper file size.
        
        memory_y = memory_y.copy().astype("float")
        max_val = max(memory_y)
        scales = ["Bytes", "KB", "MB", "GB", "TB", "PB"]
        # Find out what power of 1024 the max measured ram is
        bit_logs = math.floor(math.log(max_val, 1024))
        memory_y /= 1024 ** bit_logs

        # END:  Rescale memory_y data to proper file size.


        color = "tab:blue"
        fig, ax_memory = plt.subplots()
        ax_memory.grid()
        ax_memory.set_xlabel("Milliseconds")
        ax_memory.set_ylabel("Memory (%s)" % scales[bit_logs], color=color)
        ax_memory.plot(x, memory_y, color=color, alpha=0.8)
        ax_memory.tick_params(axis="y", labelcolor=color)
        plt.fill_between(x, memory_y, alpha=0.2, color=color)

        color = "tab:green"
        ax_cpu = ax_memory.twinx()
        ax_cpu.set_ylabel("CPU (%)", color=color)
        ax_cpu.plot(x, cpu_y, color=color, alpha=0.75, linewidth=1)
        ax_cpu.tick_params(axis="y", labelcolor=color)
        #plt.fill_between(x, cpu_y, alpha=0.2, color=color)

        #plt.tight_layout()

        # https://stackoverflow.com/a/31845332
        plt.close(fig)

        return fig
