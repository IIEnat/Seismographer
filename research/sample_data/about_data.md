# Data Overview

| Sample    | Description                                          |
|-----------|------------------------------------------------------|
| sample1   | GG.WAR8.centaur-6_1267_20220101_000000               |
| sample2   |                                                      |
| sample3   | GG.WAR30.centaur-3_7965_20220101_130000              |
| sohsample | GG.WAR8.D0.SOH_centaur-6_1267_20220102_050000        |

Each MiniSEED file sent by Carl is around 6.4MB and contains **one hour** of data for a single station.  
This implies:

- Daily size per station: 6.4 MB × 24 = **153.6 MB**  
- For 80 stations running simultaneously: 153.6 MB × 80 = **12 GB/day** (if stored)

---

## About Seismic Data 

- **network**: `GG` — Organization managing the GG group  
- **station**: `WAR8` — Station identifier (may have multiple devices per station)  
- **location**: *Empty* (not available)  
- **channel**: `HNZ` — Can be `HNX`, `HNY`, or `HNZ` representing X, Y, Z delta changes; all three streams needed for full picture  
- **starttime**: `2022-01-01T00:00:00.000000Z` (UTC)  
- **endtime**: `2022-01-01T00:59:59.996000Z` (UTC)  
- **sampling_rate**: `250.0` (samples per second)  
- **delta**: `0.004` (seconds between samples; inverse of sampling_rate)  
- **npts**: `900000` (number of data points)  
- **calib**: `1.0` (calibration factor, 1 = no change)  
- **format**: `MSEED`

### MiniSEED Attributes
- **dataquality**: `'D'` (usually 'Derived' or 'Delayed')  
- **number_of_records**: `4370` (MiniSEED blocks in this trace)  
- **encoding**: `'STEIM1'` (compression format)  
- **byteorder**: `'>'` (big endian)  
- **record_length**: `512` (bytes per block)  
- **filesize**: `6712320` (bytes for this trace)

---

### Seismic Data Stream Info
```
Trace ID: GG.WAR8..HNY
sampling_rate: 250.0
delta: 0.004
starttime: 2022-01-01T00:00:00.000000Z
endtime: 2022-01-01T00:59:59.996000Z
npts: 900000
calib: 1.0
network: GG
station: WAR8
location:
channel: HNY
mseed: AttribDict({'dataquality': 'D', 'number_of_records': 4370, 'encoding': 'STEIM1', 'byteorder': '>', 'record_length': 512, 'filesize': 6712320})
_format: MSEED
```

### Example Stream Data (first 50 entries out of 900,000)
```
[-4291 -5158 -6594 -4373 -5910 -4200 -6465 -5107 -3611 -7575 -3260 -5615
-7112 -4070 -6507 -3954 -6155 -4807 -4194 -7496 -3226 -7059 -6297 -3849
-6940 -4944 -5805 -4367 -5626 -6447 -2473 -7483 -5704 -3117 -7380 -3566
-6397 -6506 -3039 -7229 -4665 -6144 -5577 -4204 -7907 -3343 -6182 -6851
-3713 -6680]
```

---

## SOH Stream Info
```
Trace ID: GG.WAR8.D0.VM1
sampling_rate: 0.016666666666666666
delta: 60.0
starttime: 2022-01-02T05:00:00.000000Z
endtime: 2022-01-02T05:59:00.000000Z
npts: 60
calib: 1.0
network: GG
station: WAR8
location: D0
channel: VM1
mseed: AttribDict({'dataquality': 'D', 'number_of_records': 3, 'encoding': 'STEIM1', 'byteorder': '>', 'record_length': 512, 'filesize': 25088})
_format: MSEED
```

### SOH Example Stream Data

[-482079 -481836 -481783 -483854 -483740 -481948 -481896 -484031 -482058
-482022 -482017 -483938 -483904 -481869 -481903 -472073 -479899 -483878
-482036 -481874 -483830 -483873 -483761 -481991 -483945 -481991 -483821
-489967 -483861 -483773 -484050 -484045 -481991 -482020 -484022 -482087
-479543 -481972 -484010 -481996 -479906 -481836 -483995 -481905 -483964
-483998 -483864 -483850 -483778 -488001 -488023 -484069 -482118 -482213
-484079 -483990 -483871 -484053 -484141 -484033]