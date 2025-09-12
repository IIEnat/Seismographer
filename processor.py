from obspy import read

data = read("2022/Station1/file.miniseed")
print(data)
