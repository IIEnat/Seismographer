<!-- If you can read this you are viewing this document as unrendered markdown.  For readability view this document on Github or use one of the many widely available tools to render it as a PDF. -->

# Seismographer - User Manual

## Installation
1. Get a local copy of the project onto your Linux device either by cloning the Github repository or simply downloading it as a `.zip` file and extracting it.
2. Open a command-line interface like terminal and navigate to the `main/` directory within the project.
3. To install the dependencies required by the app run the following command:
```
$ pip install -r requirements.txt
```

## Configuration
For the application to connect to the seismometers, their static IP addresses must first be configured in [config.py](../main/config.py).

The variable `HOSTS` within the `# Stations / connectivity` section must be set to contain a list of seismometer IP addresses as strings.

This may require configuring a static IP address for the seismometers by connecting to the network the seismometers are on and going to `169.254.33.33` (3 channel model) or `169.254.35.35` (6 channel model).  Log in and go to settings > network > static IP.  Then type `192.168.0.XX` (for WARXX), click on seedlink server, and add a seedlink server with default settings.

## Running
1. Connect to the network that the seismometers are connected on.
  - Note that if a problem arises here the app will likely default to fake simulated data.
2. Similar to installation, open a command-line interface like terminal and navigate to the `main/` directory.
3. To start the server that runs the application run:
```
$ python3 app.py
```
- Allow a few seconds for the server to start up.
- The web app can then be accessed by opening a web browser and going to `https://127.0.0.1:5000`.
  - Often this can be shortcut by holding `ctrl` and clicking on `https://127.0.0.1:5000` in the terminal.
- The app will lauch displaying a popup 

## Usage

### Homepage: Live Seismic Map
- After waiting for data to be prepared, a standardly manipulatable map on the left shows the Perth (for testing) and Gingin area.
- Map will show the activity of connected seismometers and will update as new data arrives.
- The colour of each station indicates its relative up-down seismic activity according to the scale on the right.
  - The purple end of the colour gradient indicates a lower z-axis position, with the opposite yellow end of the spectrum indicating higher position.
  - A red coloured station indicates and error with the data that station is receiving (out of range or missing).
- Also shown on the right:
  - The network code the seismometers are on.
  - The rate the data is being streamed to the web app.
  - The rate of the calculated data for display.
  - The ID of the currently selected station.
- Clicking on a station selects it.
  - Down the bottom of the page will be a graph of the selected station's up-down seismic movement.

### Navigation 
- In the top left, clicking <u>`Go to Playback`</u> will navigate to the Playback page.
- From the Playback page in the same top left, clicking on <u>`Go to Live`</u> will navigate back to the live homepage.

### Playback Page
- Click on `Choose Files` in the top left and select `.mseed` or `.miniseed` files from the popup.
- Next click `Upload & Play`.
- On the right panel you'll see:
   - The number of files you've uploaded.
   - The temporal length of those files.
   - The currently selected seismometer.
   - Whether the selected files are currently being played.
- Down the bottom of the page you'll see a graph showing the raw seismic reading from the selected seismometer.
   - At the top of this graph is functionality to play and pause the playback as well as a slider the control the timeline and information about the file's timeline.
