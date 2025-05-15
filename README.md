![DataDrivenSailing Header](https://datadrivensailing.gitbook.io/~gitbook/image?url=https%3A%2F%2F3849893206-files.gitbook.io%2F%7E%2Ffiles%2Fv0%2Fb%2Fgitbook-x-prod.appspot.com%2Fo%2Fspaces%252F3nOHnHqWSETquXdlfpsF%252Fuploads%252FZFD75du86iGtM0usBqbX%252FHeader_DDS.png%3Falt%3Dmedia%26token%3D09a19365-ee3f-4ada-b7da-e5800a13606d&width=1248&dpr=1&quality=100&sign=cf05bd58&sv=2)

This repository provides Python scripts and modules developed for the **BoatTracker** and the central **Hub** as part of the *DataDrivenSailing* project — an open-source initiative aimed at enhancing sailing performance through data-driven insights.

The software enables efficient data acquisition, logging, and analysis, supporting sailors and coaches in making informed decisions to optimize performance.

For more information about the project, please visit the [project wiki](https://datadrivensailing.wiki).

---

## Directory Structure

### Tracker Software

```
Tracker/Software/code/
├── main.py
├── datamanager.py
├── debugprint.py
├── errordebuglogger.py
├── config/
│   ├── config.py
│   ├── mag_mmc56x3_calib.py
│   ├── mag_offsets.json
│   └── gps_SAM_M10Q_config.py
├── logfiles/
│   ├── debug.log
│   └── error.log
└── modules/
    ├── battery_MAX17048.py
    ├── gps_SAM_M10Q.py
    ├── gyroacc_LSM6DSO.py
    ├── led.py
    └── mag_mmc56x3.py
```

### Hub Software

```
hub/Software/
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
│   │   ├── debug.log
│   │   └── error.log
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
│   │   ├── debug.log
│   │   └── error.log
│   └── noderedsupport/
│       ├── pingcheck.py
│       ├── rsync.py
│       └── analysisprep.py
├── NodeRed/        # (currently empty)
└── Grafana/        # (currently empty)
```

---

## License

This project is licensed under the terms described in [LICENSE.md](LICENSE.md).
