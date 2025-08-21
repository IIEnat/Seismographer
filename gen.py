# save_data.py
import pandas as pd
import numpy as np
import time

# fake time series: 100 points
timestamps = np.arange(100) + time.time()
amplitudes = np.sin(np.arange(100) * 0.1)

df = pd.DataFrame({"time": timestamps, "amp": amplitudes})
df.to_json("trace.json", orient="records")
print("trace.json written")
