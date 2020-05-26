import cmdbench

results = cmdbench.benchmark_command("node --expose-gc test.js")
print(results)