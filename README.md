# VLT Firmware patcher
Vanilla Light Touch Firmwares. Little firmware modifications to make your day  nicer.
Project originally started by VooDooShamane (RP): [his original work](https://rollerplausch.com/threads/vlt-firmwares-in-de-22kmh-mit-neuster-vanilla-firmware-und-vieles-mehr.3197/).

I wrote this patcher based on BotoX [m365 firmware patcher](https://github.com/BotoX/xiaomi-m365-firmware-patcher).

## Supported DRVs
* DRV236
* DRV247
* DRV248
* DRV309
* DRV319
* DRV321

## Available Mods
* Brakelight
* Speed limits
* Amps / Phase currents
* Motor start speed
* No charging fix
* 30km/h speed check
* Wheelsize
* Shutdown time
* DPC (register)
* LTGM (register)
* Current raising coefficient
* Cruise control delay
* Cruise control unlock (DE)
* ReLight Mod
* DKC (replaces "No KERS")
* Pedestrian unlock

## Instructions
1. `FLASK_APP=app/__init__.py`
2. `flask run` to start the flask app

## License
Licensed under AGPLv3 (see LICENSE.md)
