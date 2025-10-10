# Seismographer - User Manual

## Installation
- Get a local copy of the project onto your Linux device either by cloning the Github repository or simply downloading it as a `.zip` file and extracting it.
- Open a command-line interface like terminal and navigate to the `main/` directory within the project.
- To install the dependancies required by the project run the following command:
```
$ pip install -r requirements.txt
```

## Running
- [Waiting on final details of map to discuss getting on network(s) before running]

- Similar to installation, open a command-line interface like terminal.
- Again navigate to the `main/` directory.
- To start the server that runs the application run:
```
$ python3 app.py
```
- The web app can then be accessed by either holding `ctrl` and clicking on `https://127.0.0.1:5000` in the terminal or by opening any web browser and going to `https://127.0.0.1:5000`.

## Usage

### Homepage: Live Seismic Map
[Waiting for map changes]
- Standardly manipulatable map on the left shows active seismic stations and updates as new data arrives.
- The colour of each station indicates its relative z-axis seismic activity according to the scale on the right.
  - The purple end of the colour gradient indicates a lower z-axis position, with the opposite yellow end of the spectrum indicating higher position.
  - A red coloured station indicates and error with the data that station is recieving ()
- Also shown on the right is the network code for the seismometers, rate the data is being streamed to the web app, the rate of the calculated data for display, and the ID of the currently selected station.
- Clicking on a station selects it.
  - Down the bottom of the page will be a graph of the selected station's up-down seismic movement.

### Navigation 
- In the top left, clicking <u>`Go to Playback`</u> will navigate to the Playback page.
- From the Playback page in the same top left, clicking on <u>`Go to Live`</u> will navigate back to the live homepage.

### Playback Page
- Click on `Choose Files` in the top left and select `.mseed` or `.miniseed` files from the popup.
- Next click `Upload & Play`.
- On the right panel you'll see
   - The number of files you've uploaded.
   - The temporal length of those files.
   - The currently selected seismometer
   - Whether the selected files are currently being played.
- Down the bottom of the page you'll see a graph showing the raw seismic reading from the selected seismometer.
   - At the top of this graph is functionality to play and pause the playback as well as a slider the control the timeline and information about the files timeline.

## Other
