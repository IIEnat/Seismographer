from flask import Flask, render_template
from python.receiver import SLClientReceiver, create_blueprint
from python.ingest import SyntheticIngest, Chan

app = Flask(__name__)

# Placeholder Data, realistically this would be relpaced by real SeedLink data from the SOH
COORDS = {
  "XX.JINJ1..BHN": (-31.3447,115.8923),
  "XX.JINJ1..BHE": (-31.3752,115.9231),
  "XX.JINJ1..BHZ": (-31.3433,115.9667),
}
rx = SLClientReceiver(coords=COORDS, metric="rms")

USE_REAL_SEEDLINK = False  

if USE_REAL_SEEDLINK:
    from python.ingest import SeedLinkIngest  # same module as SyntheticIngest

    SL_SERVER = "seedlink.example.org:18000"  # TODO: set actual host:port
    ingest = SeedLinkIngest(
        server=SL_SERVER,
        on_trace=rx.on_trace,  # keep the same callback into the receiver
    )
    ingest.start()
else:
    # Use to create the Obspy traces in ingest.py
    ingest = SyntheticIngest(
        chans=[
            Chan("XX","JINJ1","","BHN",-31.3447,115.8923,2.0,0.00),
            Chan("XX","JINJ1","","BHE",-31.3752,115.9231,3.0,0.33),
            Chan("XX","JINJ1","","BHZ",-31.3433,115.9667,5.0,0.66),
        ],
        sps=250.0,
        on_trace=rx.on_trace,
    )

ingest.start()
app.register_blueprint(create_blueprint(rx))

@app.route("/")
def home(): return render_template("home.html")

if __name__ == "__main__":
    app.run(debug=True)
