# Covid Vaccine Discord Bot

This is a Discord bot that alerts a text channel when COVID-19 vaccine appointments become available in any number of
geolocations in the United States.

Special thanks to [vaccinespotter.org](https://www.vaccinespotter.org/)

[Join the Discord server to see it in action](https://discord.gg/EcyrJqPnFy)


## Requirements

1. [Docker](https://docs.docker.com/get-docker/)
2. [Docker Compose](https://docs.docker.com/compose/install/)


## Adding new locations

To add a new location to be searched by the Discord bot, create a new json file in the "config" directory. For this
example, we will add Boston, MA, `ma-boston.json`:

```json
{
  "enabled": true,
  "channel": 1234567890,
  "publish": true,
  "latitude": 42.3600825,
  "longitude": -71.0588801,
  "radius": 10,
  "states": ["MA"],
  "test": false
}
```


### Configuration parameters

| Key | Type | Description |
| --- | ---- | ----------- |
| `enabled` | boolean | When set to `true` this location will be included in the bot's searches. |
| `channel` | int | The Discord channel's ID to send alerts to for this location. |
| `publish` | boolean | For announcement channels, setting this to `true` will publish alerts. |
| `latitude` | float | The latitude coordinate for this location. |
| `longitude` | float | The longitude coordinate for this location. |
| `radius` | int | Search radius (in miles) for nearby pharmacies. |
| `state` | array | States to include in the search, for example, a location in Kansas City may look like: `["KS", "MO"]` |
| `test` | boolean | When set to `true` the bot will always alert for at least one location (vaccine available or not), as long as there are nearby pharmacies. Useful when testing the bot. |


### Environment variables

You must set the following environment variable to run the bot. You may add environment variables through docker, the OS
or using a `.env` file in the project's root directory.

| Key | Type | Description | 
| --- | ---- | ----------- |
| `DISCORD_BOT_TOKEN` | string | The API Token for the Discord bot. |


## Running the bot

To run the bot, run the following command in the root of the project:
```
docker-compose up -d --build
```

To stop the bot:
```
docker-compose down
```


## License

The source code for the site is licensed under the MIT license, which you can find in
the LICENSE.txt file.

All graphical assets are licensed under the
[Creative Commons Attribution 3.0 Unported License](https://creativecommons.org/licenses/by/3.0/).