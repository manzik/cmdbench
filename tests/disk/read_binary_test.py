import time

for i in range(0, 100):
    filename = "files/file%s.test" % i
    with open(filename, mode='rb') as file: # binary read
        fileContent = file.read()
    print(i)