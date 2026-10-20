# Asset register extract: ESC-03

Synthetic record. Exported from the CMMS asset register on 19/09/2026.

| Field | Value |
| --- | --- |
| Asset ID | ESC-03 |
| Name | Escalator 03, Concourse to Platform 2 |
| Site | Northgate Station |
| Criticality | High. One of two escalators serving Platform 2; fixed stairs alongside. |
| Installed / modernised | 2011 / drive and controller modernisation 2019 |
| Type | Public-service escalator, reversible (tidal flow) |
| Rise / inclination / step width | 7.2 m / 30° / 1000 mm |
| Nominal speed | 0.50 m/s |
| Direction schedule | Controller timer starts the unit UP at 05:00. Station staff reverse it to DOWN at about 13:00 with the key switch. Timer stops it at 01:00. (Controller clock.) |
| Maintainer | Contractor: monthly preventive maintenance plus call-outs |

## Machinery

- **Drive:** 22 kW 4-pole induction motor; frequency inverter (2019) with a dynamic braking resistor, both in the upper machine space; helical-worm gearbox; duplex drive chain to the main drive shaft.
- **Brakes:** electromechanical service brake on the motor shaft; auxiliary brake on the main drive shaft.
- **Step band:** two step chains; tension carriage at the lower landing.
- **Handrails:** friction-wheel drive taken from the main drive shaft; tension stations in the lower newels. Left and right are named as seen when facing the upper landing from the lower landing (contractor convention).
- **Controller:** vendor safety controller in the upper machine space. Fault memory holds the newest 64 events. Status display at the upper landing.

## Safety devices (each stops the escalator when it operates)

Emergency stop buttons (upper, lower, two intermediate); comb plate switches (4); skirt switches (8); handrail inlet switches (4); handrail speed monitoring, both sides (pre-warning below 95 % of step speed; stop on a larger sustained deviation); step sag and missing step devices (upper and lower); broken drive chain; step chain tension (2); motor overtemperature; drive fault (inverter); brake release monitoring; overspeed and unintentional reversal.

## Condition monitoring (retrofit, 2025)

Gateway `cm-gateway-07` in the upper machine space, powered from the controller's auxiliary supply. It polls every 60 s, buffers locally and uploads 5-minute batches over a cellular link.

- **Read from the controller (read-only interface):** step speed, operating mode, left and right handrail speed as a percentage of step speed.
- **Gateway's own sensors:** clamp-on current transformer on the motor cable (inverter output side, RMS magnitude); gearbox oil temperature; accelerometer on the gearbox housing (1-minute RMS velocity); incoming supply voltage (line to line, at the controller isolator); 3D people counter above the upper landing.
