# Seismographer - Real Time Seismic Imaging

## Context
Seismographer was developed as a group project assigned as part of the unit [CITS3200: Professional Computing](https://teaching.csse.uwa.edu.au/units/CITS3200/) at [The University of Western Australia](https://www.uwa.edu.au/) during the second semester of 2025.  The project proposal was submitted by a client in the Physics department who needed data from a seismic array at the Gingin High Optical Power Facility collected, processed, and graphically displayed.

## Project Team
| Student Name | Student Number | GitHub Username |
|--------------|----------------|-----------------|
| Raynard      | 24006703       | IIEnat          |
| Yutong       | 23723494       | amiwaffletoday  |
| Jimmy        | 23661316       | JimmyTanUWA     |
| Kathleen     | 24091081       | kathisabella    |
| Andrew       | 23384163       | Andrew-Biggins1 |
| Aaron        | 23815248       | Attempt27       |

## Summary
Seismographer is a Flask web application developed for a Linux system that visualises real-time and historical seismic activity from seismometers.  The main page provides a live, top-down view of ground motion as it happens by displaying a map of seismic activity using a colour scale for each seismometer's readings.  This live page allows individual seismometers to be selected to simultaneously view a graph of the selected seismometer's filtered readings.  A playback page also allows `.miniseed` and `.mseed` files that store data from seismometers to be uploaded and played, displaying the same graphs as in the main page but with raw data.

## Project Setup
To **install dependancies** from ```main/``` run:
```
$ pip install -r requirements.txt
```

To **run** the app, from ```main/``` run:
```
$ python3 app.py
```

The web app can then be accessed from `https://127.0.0.1:5000`.

More detailed setup instructions can be found in [user_manual.md](docs/user_manual.md).

## Project Structure
```
Seismographer/
├── COPYING.txt                             # Project license (GNU GPL v3.0)
├── README.md                               # Project overview (this file)
├── docs/                                   # Documentation
│   ├── developer_documentation.md          # Details on implementation for future developers
│   ├── technical_user_documentation.md     # Outlines information relating to seismic data 
│   └── user_manual.md                      # How to run and use the app
└── main/                                   # Main application source code
    ├── app.py                              # Flask web application entry point
    ├── config.py                           # Configuration settings for data sources and processing
    ├── python/                             # Core backend modules
    │   ├── ingest.py                       # Signal processing (filtering, envelope detection)
    │   ├── location_retrieval.py           # Station location management and retrieval
    │   ├── playback_routes.py              # Playback functionality and endpoints
    │   └── receiver.py                     # Data ingestion from SeedLink or synthetic sources
    ├── requirements.txt                    # Python dependencies
    ├── static/                             # Static files for frontend
    │   ├── css/                            # CSS files
    │   │   └── global.css                  # Global stylesheet
    │   └── tiles/                          # Map tile images for offline map
    ├── templates/                          # HTML templates for web pages
    │   ├── home.html                       # Main map and live view
    │   ├── navbar.html                     # Navigation bar
    │   └── playback.html                   # Playback page
    ├── tests/                              # Unit and integration tests         
    │   ├── conftest.py                     # Pytest configuration and fixtures
    │   ├── test_location_fallbacks.py      # Tests for location retrieval fallback logic
    │   ├── test_playback_upload.py         # Tests for playback file upload and handling
    │   └── test_rms.py                     # Tests for RMS calculation functions
    └── uploads/                            # Directory for uploaded .miniseed and .mseed files
```


## Further Documentation
For the basics on how to use the app see [user_manual.md](docs/user_manual.md).

For details on the app's architecture, backend modules, data flow, and code structure see [developer_documentation.md](docs/developer_documentation.md).

For technical specifications on the seismic data and its processing see [technical_user_documentation.md](docs/technical_user_documentation.md).

## License
This project is licensed under the terms of the GNU General Public License v3.0.  See [COPYING.txt](COPYING.txt) for more information.
