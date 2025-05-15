# DataDrivenSailing

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
