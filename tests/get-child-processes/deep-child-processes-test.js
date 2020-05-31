let deepChildrenCount = 10;
let child_process = require('child_process');

const CHILD_PROCESSES_COUNT = 2;

// https://flaviocopes.com/javascript-sleep/
const sleep = (milliseconds) => {
	return new Promise(resolve => setTimeout(resolve, milliseconds));
};

let isChild = process.argv.indexOf("--ischild") > -1, childLevel = isChild ? process.argv[3] : 0;
//console.log(isChild ? "Running child process level " + childLevel : "Running master process");

let level = parseInt(childLevel);
let args = process.argv.slice(2);

console.log(process.pid);

if(level <= 3)
{
	for(let i = 0; i < CHILD_PROCESSES_COUNT; i++)
	{
		let child = child_process.spawn("node", 
		["deep-child-processes-test.js"].concat(["--ischild", String(level + 1)]));
		child.stdout.pipe(process.stdout);
		child.stderr.pipe(process.stderr);
    }
}

sleep(1000000);