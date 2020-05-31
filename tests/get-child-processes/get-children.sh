top_pid=$1

# Make a list of all process pids and their parent pids
ps_output=$(ps -e -o pid= -o ppid=)

# Populate a sparse array mapping pids to (string) lists of child pids
children_of=()
while read -r pid ppid ; do
    [[ -n $pid && pid -ne ppid ]] && children_of[ppid]+=" $pid"
done <<< "$ps_output"

# Add children to the list of pids until all descendants are found
pids=( "$top_pid" )
unproc_idx=0    # Index of first process whose children have not been added
while (( ${#pids[@]} > unproc_idx )) ; do
    pid=${pids[unproc_idx++]}       # Get first unprocessed, and advance
    pids+=( ${children_of[pid]-} )  # Add child pids (ignore ShellCheck)
done

# Do something with the list of pids (here, just print them)
printf '%s\n' "${pids[@]}"