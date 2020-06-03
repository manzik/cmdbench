import sys
import os
sys.path.append("../..")

import cmdbench

strain_name = "2014C-3598"

# Remove mccortex output file if it exists
if os.path.exists("%s.ctx" % strain_name):
  os.remove("%s.ctx" % strain_name)
# Remove bloome filters if they exist
if os.path.exists("%s.ctx" % strain_name):
  os.remove("%s.ctx" % strain_name)


os.system("export BIGSI_CONFIG=berkleydb.yaml")

command_mccortex = "mccortex 17 build --nkmers 74000000 --threads 1 --kmer 17 --mem 20G --sample {0} --seq {0}.fastq.gz {0}.ctx"
benchmark_results_mccortex = cmdbench.benchmark_command(command_mccortex.format(strain_name + "_1"))
print(command_mccortex)
print(benchmark_results_mccortex.get_single_iteration())
print(benchmark_results_mccortex.get_single_iteration().process.stderr_data)

benchmark_results_mccortex = cmdbench.benchmark_command(command_mccortex.format(strain_name + "_2"))
print(command_mccortex)
print(benchmark_results_mccortex.get_single_iteration())
print(benchmark_results_mccortex.get_single_iteration().process.stderr_data)

command_bloom_filters = "bigsi bloom {0}.ctx bloom-filters/{0}.bloom --config berkleydb.yaml"

benchmark_results_bloom_filters = []

benchmark_results_bloom_filters += cmdbench.benchmark_command(command_bloom_filters.format(strain_name + "_1"))
print(command_bloom_filters)
print(benchmark_results_bloom_filters.get_single_iteration())
print(benchmark_results_bloom_filters.get_single_iteration().process.stderr_data)

benchmark_results_bloom_filters = cmdbench.benchmark_command(command_bloom_filters.format(strain_name + "_2"))
print(command_bloom_filters)
print(benchmark_results_bloom_filters.get_single_iteration())
print(benchmark_results_bloom_filters.get_single_iteration().process.stderr_data)

command_index_bloom_filters = "bigsi build -b  bloom-filters/{0}_1.bloom -b bloom-filters/{0}_2.bloom"
benchmark_results_bloom_filters = cmdbench.benchmark_command(command_bloom_filters.format(strain_name))
print(command_bloom_filters)
print(benchmark_results_bloom_filters.get_single_iteration())
print(benchmark_results_bloom_filters.get_single_iteration().process.stderr_data)