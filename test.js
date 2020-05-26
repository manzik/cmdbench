let fs = require("fs");
let child_process = require('child_process');

let isChild = process.argv.indexOf("--ischild") > -1, childNum = isChild ? process.argv[3] : 0;
console.log(isChild ? "Running child process #" + childNum : "Running master process");

const CHILD_PROCESSES_COUNT = 8; // Number of times to run the same script as children
const WAIT_MS = 1000;
const ERROR_CHANCE = 0.0;
const TEST_FILE_SIZE_KB = 1024;
const LOOP_COUNT = 10000000;
const TEST_FILE_SIZE_PATH = `file${childNum}.test`;

// https://flaviocopes.com/javascript-sleep/
const sleep = (milliseconds) => {
	return new Promise(resolve => setTimeout(resolve, milliseconds));
};

async function main()
{
	let output = "";

	// Randomly show error for testing purposes
	let encounteredError = Math.random() < ERROR_CHANCE;

	// FILL MEMORY
	// CPU USE START
	for(let i = 0; i < LOOP_COUNT; i++)
		output += Math.round(Math.random() + Math.random()) + "\n";
	// CPU USE END

	if(!isChild && encounteredError)
	{
		process.stderr.write(`Encountered test error process #${childNum}\n`);
		process.exit(10);
	}
	else
	{
		await sleep(WAIT_MS);
		// FREE MEMORY (not reliable)
		output = undefined;
		global.gc();
		// WAIT 1 SEC
		await sleep(WAIT_MS);
		
		// FILL BUFFER
		// WRITE TO DISK
		let testData = Buffer.alloc(1024*TEST_FILE_SIZE_KB);
		for(let i = 0; i < testData.length; i++)
			testData.fill(Math.random().toString(36)[0], i, i + 1)
		fs.writeFileSync(TEST_FILE_SIZE_PATH, testData);

		// READ FROM DISK
		testData = fs.readFileSync(TEST_FILE_SIZE_PATH);

		// DELETE FROM DISK
		fs.unlinkSync(TEST_FILE_SIZE_PATH);

		let args = process.argv.slice(2);

		// Spawn children if is master process
		if(args.indexOf("--ischild") == -1)
			for(let i = 0; i < CHILD_PROCESSES_COUNT; i++)
			{
				let child = child_process.spawn("node", 
				["--expose-gc", "test.js"].concat(args).concat(["--ischild", String(i + 1)]));
				child.stdout.pipe(process.stdout);
				child.stderr.pipe(process.stderr);
			}
	}
}
main();
