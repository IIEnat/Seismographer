<!-- If you can read this you are viewing this document as unrendered markdown.  For readability view this document on Github or use one of the many widely available tools to render it as a PDF. -->

# Seismographer - Technical User Documentation

## Configuration Options
See **Configuration Reference** in [developer_documentation.md](developer_documentation.md)

## Filtering

### Band Pass
The app uses a band pass filter to produce coherent waveforms on the main pages graphs.

**Configuration**: The band-pass frequency range is set in `config.py` as `BAND = (0.05, 0.10)`, meaning only frequencies between 0.05 Hz and 0.10 Hz are retained.

**Filter Setup**: In [`reciever.py`](../main/python/reciever.py) within the `StationProcessor.__init__()` method, a 4th-order Butterworth band-pass filter is created using SciPy.

**Filtering Data**: When new data arrives the `_bandpass()` method applies the filter:

### Enveloping
Envelope extraction is performed after band-pass filtering, again within the `StationProcessor` class in [`receiver.py`](../main/python/reciever.py).  It is the enveloped data that is used to display the colour of each seismometer.

**Analytic Envelope Calculation**: The `_env_native()` method computes the analytic envelope of the band-passed signal using the Hilbert transform.  This produces a smooth, non-negative curve representing the instantaneous amplitude of the signal.

**Smoothing**: To reduce ripple and stabilize the envelope, a zero-phase low-pass Butterworth filter (~0.3 Hz cutoff) is applied.  This ensures the envelope is gently smoothed without introducing phase distortion.

**Decimation**: The envelope, originally at the native sampling rate, is then downsampled to the target UI rate (5 Hz) using zero-phase decimation in `_env_5hz_from_block()`.  This makes the envelope suitable for real-time display and further analysis.

## RMS (Root Mean Square)
RMS is used in [`playback_routes.py](../main/python/playback_routes.py) within `playback_stats()` to obtain a average signal amplitude for colour representation on the playback map.   The RMS value is computed by squaring each sample in the signal, averaging these squares over the window, and then taking the square root of the result. This is typically done using NumPy functions for efficiency.
