from cmdbench.result import BenchmarkResults
from cmdbench.utils import BenchmarkDict
from cmdbench.core import benchmark_command_generator
from cmdbench.keys_dict import key_readables
from tqdm import tqdm
import numbers
import numpy as np
import pkg_resources
import click
import time
import json

PRINTING_PRECISION = 3

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
       Note: Make sure you enter your command after entering the options.
       

       You can wrap your command around single or double quotations if it contains one or the other.
       Replacing inner double quotations with "" in windows and \\\" in linux.
       For example:

       Linux: cmdbench -i 5 "python -c \\"import time; time.sleep(2)\\""
       
       Windows: cmdbench -i 5 "python -c ""import time; time.sleep(2)""\"
       
       If no printing options are specified, statistics will be printed for more than 1 iterations, and the first iteration for only 1 iteration."""

    np.set_printoptions(threshold=15)

    click.echo("Benchmarking started..")
    benchmark_results = BenchmarkResults()
    benchmark_generator = benchmark_command_generator(" ".join(command), iterations)
    t = tqdm(range(iterations))
    for i in t:
        benchmark_result = next(benchmark_generator)
        benchmark_results.add_benchmark_result(benchmark_result)
        last_runtime = benchmark_result.get_first_iteration().process.execution_time
        last_runtime = round(last_runtime, PRINTING_PRECISION)
        t.set_description("Last runtime:  %s seconds" % last_runtime)
        t.refresh()
    click.echo("Benchmarking done.")
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
        print_benchmark_dict(benchmark_results.get_statistics(), "Statistics")

    if(kwargs["print_averages"]):
        print_benchmark_dict(benchmark_results.get_averages(), "Averages")

    if(kwargs["print_values"]):
        print_benchmark_dict(benchmark_results.get_values_per_attribute(), "Values")

    if(kwargs["print_first_iteration"]):
        print_benchmark_dict(benchmark_results.get_first_iteration(), "First Iteration")

    if(kwargs["print_all_iterations"]):
        click.secho("====> %s <====\n" % "All Iterations", fg="green")
        for ind, iteration in enumerate(benchmark_results.iterations):
            print_benchmark_dict(BenchmarkDict.from_dict(iteration), "Iteration #%s" % (ind + 1), indentation = 4, title_fg_color="magenta")

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

def print_benchmark_dict(bdict, title, title_fg_color = "green", indentation = 0):
    click.secho(" " * indentation + "====> %s <====" % title + "\n", fg = title_fg_color, bold = True)
    print_benchmark_dict_to_readable(bdict, indentation)

key_print_order = ["process", "cpu", "memory", "disk", "time_series"]
def print_benchmark_dict_to_readable(bdict, indentation = 0):
    
    remaining_keys = list(bdict.keys())
    while(len(remaining_keys) != 0):
        # START: Figure out if the key is in the list of keys to be printed in a certain order
        found_priority = False
        target_key = remaining_keys[0]
        for priority_key in key_print_order:
            if priority_key in remaining_keys:
                target_key = priority_key
                found_priority = True
                break
        remaining_keys.remove(target_key)
            
        key = target_key
        value = bdict[key]
        # END: Figure out if the key is in the list of keys to be printed in a certain order


        key_readables_values = key_readables[key] if key in key_readables.keys() else None

        key_formatted = key if key_readables_values is None else key_readables_values[0]
        key_formatted = key_formatted[0].upper() + key_formatted[1:]
        unit_str = "" if key_readables_values is None or len(key_readables_values) < 2 else key_readables_values[1]

        is_bdict = isinstance(value, BenchmarkDict)
        unit_comes_before = is_bdict

        val_is_bdict = isinstance(value, BenchmarkDict)
        if(val_is_bdict):
            unit_str_final = (" (%s)" % unit_str if len(unit_str) > 0 else "")

            indent_line(indentation)
            click.secho(key_formatted + unit_str_final, fg = "yellow", nl = False)
            click.echo(": "  + "\n", nl = False)

            print_benchmark_dict_to_readable(value, indentation + 4)
        else:
            unit_str_final = (" " + unit_str  if len(unit_str) > 0 else "")

            indent_line(indentation)
            click.secho(key_formatted, fg = "cyan", nl = False)
            final_value = None
            if(isinstance(value, numbers.Number)):
                final_value = str(round(value, PRINTING_PRECISION))
            else:
                final_value = value.__repr__()
            click.echo(": " + final_value + unit_str_final + "\n", nl = False)
    click.echo()

def indent_line(indentation):
    click.echo(" " * indentation, nl = False)

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)

if __name__ == "__main__":
    benchmark(prog_name='cmdbench')