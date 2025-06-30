![DataDrivenSailing Header](https://datadrivensailing.gitbook.io/~gitbook/image?url=https%3A%2F%2F3849893206-files.gitbook.io%2F%7E%2Ffiles%2Fv0%2Fb%2Fgitbook-x-prod.appspot.com%2Fo%2Fspaces%252F3nOHnHqWSETquXdlfpsF%252Fuploads%252FZFD75du86iGtM0usBqbX%252FHeader_DDS.png%3Falt%3Dmedia%26token%3D09a19365-ee3f-4ada-b7da-e5800a13606d&width=1248&dpr=1&quality=100&sign=cf05bd58&sv=2)

![Static Badge](https://img.shields.io/badge/release-first%20release%20coming%20soon-%23e2007a)
![Static Badge](https://img.shields.io/badge/%20-Documented%20on%20GitBook-%23E2007A?logo=gitbook&logoColor=white&labelColor=grey&link=https%3A%2F%2Fdatadrivensailing.gitbook.io%2Fwiki)
![Static Badge](https://img.shields.io/badge/python-V3.13-%23e2007a)
![Static Badge](https://img.shields.io/badge/software-NoderRED%2C%20InfluxDB%202%2C%20SQLite3%2C%20Mosquitto%2C%20Grafana-%23e2007a)



This repository provides Python scripts and modules developed for the **BoatTracker** and the central **Hub** as part of the *DataDrivenSailing* project — an open-source initiative aimed at enhancing sailing performance through data-driven insights.

The software enables efficient data acquisition, logging, and analysis, supporting sailors and coaches in making informed decisions to optimize performance.

For more information about the project, please visit the project wiki: [https://datadrivensailing.wiki](https://datadrivensailing.wiki).

---

## Directory Structure

### Software

```
Software/
├── code/
│   ├── main.py
│   ├── datamanager.py
│   ├── debugprint.py
│   ├── errordebuglogger.py
│   ├── config/
│   │   ├── config.py
│   │   ├── mag_mmc56x3_calib.py
│   │   ├── mag_offsets.json
│   │   └── gps_SAM_M10Q_config.py
│   ├── logfiles/
│   │   ├── debug.txt
│   │   └── error.txt
│   └── modules/
│       ├── gps_SAM_M10Q.py
│       ├── gyroacc_LSM6DSO.py
│       ├── led.py
│       └── mag_mmc56x3.py
├── code_nodered/
│   ├── main.py
│   ├── api.py
│   ├── errordebugloggernodered.py
│   ├── logfiles/
│   │   ├── debug.txt
│   │   └── error.txt
│   └── noderedsupport/
│       ├── pingcheck.py
│       ├── rsync.py
│       └── analysisprep.py
├── NodeRed/
│   ├── Screenhots/[Screenshots of all flows]
│   ├── NodeRed_FlowBackup_ALL.json
└── Grafana/
│   ├── BoatliveDashboard.json
```
The repository follows a **single–code-base** strategy: the same Python 3 sources run on every device, while behaviour is selected at start-up by a Python configuration file (`code/config/config.py`). Only brief functional roles are sketched below; full in-line documentation is available in the respective scripts.

- **`code/config/` –**  
  `config.py` stores all device-specific parameters: identifier, device type, sensor orientation, log rate, debug level, and more. Auxiliary calibration utilities generate persistent offset files (e.g. `mag_offsets.json`) that are referenced at run-time. Changing hardware therefore requires only one script edit and a matching I²C address update.

- **`code/main.py` –**  
  Executed as a *systemd* service on the Raspberry Pi, this launcher creates the sensor, logging, and communication threads, handles uncaught exceptions, and implements the GNSS-synchronised acquisition loop discussed in § *Data Frequency*.

- **`code/datamanager.py` –**  
  Initialises the local SQLite database, queues live records to the MQTT broker, and prevents RAM exhaustion. Transmission state and failures are reported through the unified error logger and status LED.

- **`code/debugprint.py` –**  
  Utility for interactive testing: prints arbitrary variables, toggles the multicolour LED, and can output raw NMEA sentences. Helpful during sensor calibration and diagnostics.

- **`code/errordebuglogger.py` –**  
  Centralised logging backend; always records errors and optionally records debug messages when enabled in `config.py`. Two rolling text files (`debug.txt`, `error.txt`) reside in `code/logfiles/` and trim themselves before exceeding 1 000 lines.

- **`code/modules/` –**  
  Self-contained drivers for each sensor. Substituting a breakout board therefore requires edits only inside the corresponding module and a single line in `config.py`.

- **`code_nodered/` –**  
  Executed exclusively on the **hub**. `main.py` supervises a lightweight REST API (`api.py`) through which Node-RED flows trigger local Python utilities. Support scripts in `noderedsupport/` include  
  `pingcheck.py` (device reachability),  
  `rsync.py` (incremental log synchronisation), and  
  `fileprep_boat.py` (conversion of SQLite logs to CSV/JSON for **Njord Analytics**).  
  Error and debug handling mirrors the implementation in the main `code/` folder.
---

## License

This project is licensed under the terms described in [LICENSE.md](LICENSE.md).
