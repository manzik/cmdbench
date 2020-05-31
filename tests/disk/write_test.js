let fs = require("fs");

const TEST_FILE_SIZE_KB = 128;

let data = [];

let disk_mode = "write";

for(let i = 0; i < 100; i++)
{
    const TEST_FILE_NAME = __dirname + `/files/file${i}.test`;

    if(disk_mode == "write")
    {
        let testData = Buffer.alloc(1024*TEST_FILE_SIZE_KB);
        for(let i = 0; i < testData.length; i++)
    	    testData.fill((Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15))[0], i, i + 1)
        fs.writeFileSync(TEST_FILE_NAME, testData);
    }
    else if(disk_mode == "read")
        data.push(fs.readFileSync(TEST_FILE_NAME));
}
console.log(data);