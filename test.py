from fastapi import FastAPI
from obspy import read
import pandas as pd

app = FastAPI()

@app.get("/data")
def get_data():
    tr = read("2022/Station1/file.miniseed")[0]
    df = pd.DataFrame({
        "time": tr.times("timestamp"),
        "amp": tr.data
    })
    return df.to_dict(orient="records")
