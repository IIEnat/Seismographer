<!-- If you can read this you are viewing this document as unrendered markdown.  For readability we recommend viewing this document on Github or using one of the many widely available tools to render it as a PDF. -->

# Seismographer - Technical User Documentation

## Fallback

##

## Filtering

### Band Pass
Band-pass filtering in this app is performed in the `StationProcessor` class within receiver.py. Here’s how it works:

**Configuration**:
The band-pass frequency range is set in `config.py` as `BAND = (0.05, 0.10)`, meaning only frequencies between 0.05 Hz and 0.10 Hz are retained.

**Filter Setup**:  
In the `StationProcessor.__init__` method, a 4th-order Butterworth band-pass filter is created using SciPy:
```python
lo, hi = band
wn = (max(lo, 1e-4) / (self.fs * 0.5), max(hi, 2e-4) / (self.fs * 0.5))
self._sos = signal.butter(4, wn, btype="bandpass", output="sos")
self._zi = signal.sosfilt_zi(self._sos) * 0.0
```

**Filtering Data**:  
When new data arrives, the `_bandpass` method applies the filter:
```python
def _bandpass(self, x: np.ndarray) -> np.ndarray:
  y, self._zi = signal.sosfilt(self._sos, np.asarray(x, dtype=np.float64), zi=self._zi)
  return y
```

This uses the filter coefficients (`self._sos`) to process the incoming signal and maintain filter state (`self._zi`).

**Summary:**:
The app uses a Butterworth band-pass filter (0.05–0.10 Hz) to process seismic data, implemented via SciPy’s `signal.butter` and `signal.sosfilt` functions. The filter is applied to each incoming data chunk before further processing.

### Envelop

Envelope extraction in this app is performed after band-pass filtering, within the `StationProcessor` class in `receiver.py`. The process is as follows:

1. **Analytic Envelope Calculation**:  
   The `_env_native` method computes the analytic envelope of the band-passed signal using the Hilbert transform:
   ````python
   // ...existing code...
   env = np.abs(signal.hilbert(band_native.astype(np.float64)))
   // ...existing code...
   ````
   This produces a smooth, non-negative curve representing the instantaneous amplitude of the signal.

2. **Smoothing**:  
   To reduce ripple and stabilize the envelope, a zero-phase low-pass Butterworth filter (~0.3 Hz cutoff) is applied:
   ````python
   // ...existing code...
   nyq = max(1e-6, 0.5 * self.fs)
   wc = min(0.3 / nyq, 0.99)
   sos = signal.butter(2, wc, btype="low", output="sos")
   env = signal.sosfiltfilt(sos, env)
   // ...existing code...
   ````
   This ensures the envelope is gently smoothed without introducing phase distortion.

3. **Decimation**:  
   The envelope, originally at the native sampling rate, is then downsampled to the target UI rate (5 Hz) using zero-phase decimation:
   ````python
   // ...existing code...
   def _env_5hz_from_block(self, band_native_block: np.ndarray) -> np.ndarray:
       env_native = self._env_native(band_native_block)
       return self._decimate_to_5hz(env_native)
   // ...existing code...
   ````
   This makes the envelope suitable for real-time display and further analysis.

**Summary:**  
The app computes the analytic envelope of the band-passed signal using the Hilbert transform, smooths it with a low-pass filter, and then decimates it to 5 Hz for UI streaming. This process provides a clear, stable representation of signal amplitude over time.

## For details on configuration options see **Configuration Reference** in [developer_documentation.md](developer_documentation.md)
