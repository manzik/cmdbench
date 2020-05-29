import time
from collections import namedtuple, defaultdict
import numpy as np
from beeprint import pp


class BenchmarkData():
    _iterations = []
    def __init__(self, iterations):
        self._iterations = iterations
    def get_single_iteration(self):
        return BenchmarkDict.from_dict(self._iterations[0])
    def get_iterations(self):
        return BenchmarkDict.from_dict(self._iterations)
    def get_values_per_attribute(self):
        value_per_attribute_values = {}
    def get_statistics(self):
        pass
    def get_averages(self):
        pass
    def get_resources_plot(self):
        pass

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
    def from_dict(obj, first = True):
        attr_dict = BenchmarkDict()
        for key, value in obj.items():
            attr_dict_pair_value = BenchmarkDict.get_dict_value_converted(value)
            attr_dict.__setattr__(key, attr_dict_pair_value)
            if(first):
                print(key, attr_dict_pair_value)
        return attr_dict
    @staticmethod
    def get_dict_value_converted(value):
        attr_dict_pair_value = None
        if(isinstance(value, dict)):
            attr_dict_pair_value = BenchmarkDict.from_dict(value, False)
        elif(isinstance(value, BenchmarkDict)):
            attr_dict_pair_value = BenchmarkDict.from_dict(value, False)
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
        
        data = np.array(data)

        if type(data) is np.ndarray:
            if(len(data > 0)):
                mean_val = np.mean(data)
                sd_val = np.std(data)
                min_val = np.min(data)
                max_val = np.max(data)
        
        self.data = data
        self.mean, self.sd, self.min, self.max = mean_val, sd_val, min_val, max_val
    def __repr__(self):
        return "(mean: %(mean)s, SD: %(sd)s, min: %(min)s, max: %(max)s)" % {
            "mean": self.mean, "sd": self.sd,
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