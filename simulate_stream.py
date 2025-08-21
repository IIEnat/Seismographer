# simulate_stream.py
import pandas as pd
import numpy as np
import time
import json

# 1000 points of synthetic data
n_points = 1000
for i in range(n_points):
    # simulate a waveform sample
    sample = np.sin(i * 0.1)
    timestamp = time.time()
    data_point = {"time": timestamp, "amp": sample}

    # append to a JSON file
    with open("stream.json", "w") as f:
        json.dump([data_point], f)

    print(f"Sent: {data_point}")
    time.sleep(0.1)  # 10 samples per second
