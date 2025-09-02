## How to Run
Install dependencies 

```
pip install -U flask obspy numpy
```

Change directory to /main/ and run using
```
flask run
```

## Project Structure & Description
```
.
├── app.py                              # changed to accomodate mock-ups
├── python
│   ├── __pycache__
│   │   ├── ingest.cpython-313.pyc
│   │   └── receiver.cpython-313.pyc
│   ├── ingest.py
│   └── receiver.py
├── requirements.txt
├── static
│   └── css
│       ├── global.css                  # edited main file
│       ├── global_mock1.css            # NEW file for mock1
│       └── global_mock2.css            # NEW file for mock2
└── templates
    ├── beamforming.html                # NEW placeholder page
    ├── home.html                       # edited main page
    ├── home_mock1.html                 # NEW file for mock1
    ├── home_mock2.html                 # NEW file for mock2
    └── manual.html                     # NEW placeholder page
```

## Explanation

`http://127.0.0.1:5000` --> shows `home.html`

`http://127.0.0.1:5000/mock1` --> shows `home_mock1.html`

`http://127.0.0.1:5000/mock2` --> shows `home_mock2.html`

`http://127.0.0.1:5000/beamforming` --> shows `beamforming.html`

`http://127.0.0.1:5000/manual` --> shows `manual.html`

OR 

Click the buttons on the website's header for navigation! 
