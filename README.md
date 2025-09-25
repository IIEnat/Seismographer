# Seismographer - Real Time Seismic Imaging 
Seismographer is an interactive tool that visualises real-time seismic activity using live data feeds. Built for researchers for monitoring gravitational waves, this project translates seismic signals into intuitive color-coded maps, providing a live, top-down view of ground motion as it happens.

## Key Features 
- Real-time Data: Connects to seismometers using SeedLink and processes streams via ObsPy.  
- Dynamic Mapping: Visualizes ground motion on an interactive map.  
- Color-coded Intensity: Seismic intensity is rendered using color gradients for easy interpretation.  
- Live Updates: The map auto-refreshes as new seismic data arrives.  
- Customisable Views: Filter by station or time window.  

## Technologies Used
A web-app built using Flask and typical webdev technologies:
- Obspy, numpy, seedlink for data aggregation in Python.
- HTML, CSS, JS for frontend.

## Project Team
| Student Name | Student Number | GitHub Username   |
|--------------|----------------|-------------------|
| Raynard      | 24006703       | IIEnat            |
| Yutong       | 23723494       | amiwaffletoday    |
| Jimmy        | 23661316       | JimmyTanUWA       |
| Aaron        | 23815248       | Attempt27         |
| Andrew       | 23384163       | Andrew-Biggins1   |
| Kathleen     | 24091081       | kathisabella      |

## Project Setup
To **install dependancies** change directory to ```/main/``` and run:
```
$ pip install -r requirements.txt
```

To **run** the app, from the same ```/main/``` directory run:
```
$ flask run
```

## Project Structure
```
├── README.md
├── main/
│   ├── app.py
│   ├── config.py
│   ├── python/
│   │   ├── ingest.py
│   │   └── receiver.py
│   ├── requirements.txt
│   ├── static/
│   │   └── css/
│   │       └── global.css
│   ├── templates/
│   │   ├── home.html
│   │   ├── navbar.html
│   │   └── playback.html
│   └── uploads/
```
