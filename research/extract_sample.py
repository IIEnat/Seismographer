from obspy import read
import os

os.chdir('sample_data')
filename = "sample1.miniseed"

st = read(filename)

for tr in st:
    print(f"Trace ID: {tr.id}")
    for key, value in tr.stats.items():
        print(f"{key}: {value}")
    print("-" * 40)

for tr in st:
    print(tr.data[:50]) 
