from cmdbench.result import BenchmarkResults
from cmdbench.utils import BenchmarkDict
from cmdbench.core import benchmark_command_generator
from cmdbench.keys_dict import key_readables
from tqdm import tqdm
import numpy as np
import pkg_resources
import click
import time
import json

__version__ = pkg_resources.require("cmdbench")[0].version
@click.version_option(__version__)

@click.option("--print-averages", "-a", default = False, is_flag = True, show_default=True,
    help="Prints averages of each type of resources (over all iterations).")
@click.option("--print-values", "-v", default = False, is_flag = True, show_default=True,
    help="Prints a list of values per type of resources (over all iterations).")
@click.option("--print-first-iteration", "-f", default = False, is_flag = True, show_default=True,
    help="Prints values for each type of resources (for the first iteration only).")
@click.option("--print-all-iterations", "-A", default = False, is_flag = True, show_default=True,
    help="Prints values for each type of resources (for each iteration).")
@click.option("--print-statistics", "-s", default = False, is_flag = True, show_default=True,
    help="Prints mean, stdev, min and max value of each type of resources (over all iterations).")

@click.option("--save-json", "-j", default = None, type = click.File('w'),
    help="File address to save the collected data as JSON.")
@click.option("--save-plot-size", "-P", default = (15, 5), type = (click.IntRange(1), click.IntRange(1)), show_default=True,
    help="Width and height of the saving plot. Works if --save-plot is specified.")
@click.option("--save-plot", "-p", default = None, type=click.File('wb'),
    help="File address to save a plot of the command's resource usage over time (CPU + Memory).")

@click.option("--iterations", "-i", default = 1, type = click.IntRange(1), show_default=True,
    help="Number of iterations to get benchmarking results for the target command.")

@click.argument("command", required = True, type = click.UNPROCESSED, nargs = -1)


@click.command(context_settings=dict(
    allow_extra_args = True,
    allow_interspersed_args = False
))
def benchmark(command, iterations, **kwargs):
    """Performs CPU, memory and disk usage benchmarking on the target command.
       Note: Make sure you write your command after writing the options.
       
       You can wrap your command around single or double quotations if it contains one or the other.
       Replacing inner double quotations with \""" in windows and \\\" in linux.
       For example in linux:

       cmdbench -i 5 "node -e \\"setTimeout(()=>{console.log("done");}, 2000)\\""
       
       If no printing options are specified, statistics will be printed for more than 1 iterations, and the first iteration for only 1 iteration."""

    np.set_printoptions(threshold=15)

    click.echo("Started benchmarking..")
    benchmark_results = BenchmarkResults()
    benchmark_generator = benchmark_command_generator(" ".join(command), iterations)
    t = tqdm(range(iterations))
    for i in t:
        benchmark_result = next(benchmark_generator)
        benchmark_results.add_benchmark_result(benchmark_result)
        t.set_description("Last runtime:  %s seconds" % benchmark_result.get_first_iteration().process.execution_time)
        t.refresh()
    click.echo("Done benchmarking.")
    click.echo()

    option_keys = ["print_statistics", "print_averages", "print_values", "print_first_iteration", "print_all_iterations"]

    # Print statistics if user did not tell us what info to print
    printing_any = False
    for option_key in option_keys:
        if(kwargs[option_key]):
            printing_any = True
            break
    if not printing_any:
        if(iterations > 1):
            kwargs["print_statistics"] = True
        else:
            kwargs["print_first_iteration"] = True
    
    if(kwargs["print_statistics"]):
        click.echo(get_benchmark_dict(benchmark_results.get_statistics(), "Statistics"))

    if(kwargs["print_averages"]):
        click.echo(get_benchmark_dict(benchmark_results.get_averages(), "Averages"))

    if(kwargs["print_values"]):
        click.echo(get_benchmark_dict(benchmark_results.get_values_per_attribute(), "Values"))

    if(kwargs["print_first_iteration"]):
        click.echo(get_benchmark_dict(benchmark_results.get_first_iteration(), "First Iteration"))

    if(kwargs["print_all_iterations"]):
        click.echo("====> %s <====" % "All Iterations")
        for ind, iteration in enumerate(benchmark_results.iterations):
            click.echo(get_benchmark_dict(iteration, "Iteration #%s" % (ind + 1)))

    save_plot_value = kwargs["save_plot"]
    if(save_plot_value is not None):
        save_plot_sizes = kwargs["save_plot_size"]
        save_plot_width = save_plot_sizes[0]
        save_plot_height = save_plot_sizes[1]

        fig = benchmark_results.get_resources_plot(save_plot_width, save_plot_height)
        fig.savefig(save_plot_value)

    save_json_value = kwargs["save_json"]
    if(save_json_value is not None):
        json.dump(benchmark_results.iterations, save_json_value, cls=NumpyEncoder)

    click.echo("Done.")

def get_benchmark_dict(bdict, title):
    result = ""
    result += "====> %s <====" % title + "\n\n"
    result += benchmark_dict_to_readable(bdict)
    return result

def benchmark_dict_to_readable(bdict, indentation = 0):
    result = ""
    for key, value in bdict.items():
        key_readables_values = key_readables[key] if key in key_readables.keys() else None

        key_formatted = key if key_readables_values is None else key_readables_values[0]
        key_formatted = key_formatted[0].upper() + key_formatted[1:]
        unit_str = "" if key_readables_values is None or len(key_readables_values) < 2 else key_readables_values[1]

        is_bdict = isinstance(value, BenchmarkDict)
        unit_comes_before = is_bdict

        unit_value_before =(" (%s)" % unit_str if unit_comes_before and len(unit_str) > 0 else "")
        unit_value_after = (" %s" % unit_str if not unit_comes_before and len(unit_str) > 0 else "") + "\n"

        result += " " * indentation + key_formatted + unit_value_before + ": " + value_to_readable(value, indentation + 4) + unit_value_after

    return result

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)

def value_to_readable(val, indentation):
    result = None
    if(isinstance(val, BenchmarkDict)):
        result = " " * indentation + "\n" + benchmark_dict_to_readable(val, indentation)
    else:
        result = val.__repr__()
    return  result

if __name__ == "__main__":
    benchmark(prog_name='cmdbench')