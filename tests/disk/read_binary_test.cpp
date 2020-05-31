#include <iostream>
#include <sstream>
#include <fstream>
#include <string.h>
#include <vector>

using namespace std;

int readFile(string path);
string toString(int number);

int main()
{
	int totalFileBytes = 0;

    for(int i = 0; i < 100; i++)
        totalFileBytes += readFile("files/file" + toString(i) + ".test");
    
    cout << "Total file bytes: " << totalFileBytes << endl;
	return 0;
}

int readFile(string path)
{

    ifstream instream;

    instream.open(path, ios::binary);

    if(instream.fail())
    {
        cout << "File error";
        return 1;
    }

    vector<unsigned char> bytes;
    while(!instream.eof())
    {
        unsigned char byte;
        instream >> byte;
        bytes.push_back(byte);
    }

    instream.close();

    return bytes.size();
}

// https://stackoverflow.com/a/13636164
string toString(int number)
{
    std::ostringstream stm;
    stm << number;
    return stm.str();
}