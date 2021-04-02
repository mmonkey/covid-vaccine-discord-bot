import argparse
import discord
import json
import os
import pytz
import requests
import sys
from datetime import datetime
from discord.ext import tasks
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Load configs
configs = []
files = [file for file in os.listdir('config/') if file.endswith('.json')]
for file in files:
    with open(f'config/{file}') as f:
        configs.append(json.load(f))
        print(f'config file loaded: {file}')


# Discord bot
class CovidVaccineBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.locations = []
        self.availability = {}
        self.newly_available = []
        self.message = ''
        self.check_for_vaccine_availability_task.start()

    async def on_ready(self):
        print(f'Logged in as {self.user.name} ({self.user.id})')

    def get_vaccine_availability(self, latitude, longitude, radius):
        url = 'https://www.hy-vee.com/my-pharmacy/api/graphql'
        query = '''
            query SearchPharmaciesNearPointWithCovidVaccineAvailability($latitude: Float!, $longitude: Float!, $radius: Int! = 10) {
                searchPharmaciesNearPoint(latitude: $latitude, longitude: $longitude, radius: $radius) {
                    distance
                    location {
                        locationId
                        name
                        nickname
                        phoneNumber
                        businessCode
                        isCovidVaccineAvailable
                        covidVaccineEligibilityTerms
                        address {
                            line1
                            line2
                            city
                            state
                            zip
                            latitude
                            longitude
                            __typename
                        }
                        __typename
                    }
                    __typename
                }
            }
        '''
        response = requests.post(url, json={
            'query': query,
            'variables': {
                'latitude': latitude,
                'longitude': longitude,
                'radius': radius,
            }
        })

        if response.status_code == 200:
            json_data = json.loads(response.text)
            self.locations = list(map(lambda location: location['location'], json_data['data']['searchPharmaciesNearPoint']))

        else:
            print(f'Error getting vaccine availability: {response.text}')
            self.locations = []

    def get_newly_available_locations(self, is_test=False):
        self.newly_available = []

        for location in self.locations:
            prev_avail = self.availability[location['locationId']] if location['locationId'] in self.availability else False

            if location['isCovidVaccineAvailable'] and not prev_avail:
                self.newly_available.append(location)

            if not len(self.newly_available) and is_test:
                self.newly_available.append(location)

            self.availability[location['locationId']] = location['isCovidVaccineAvailable']

    def message_start(self):
        self.message = '@everyone :syringe: appointments available!'

    def message_location(self, location):
        name = location['nickname'] if location['nickname'] else location['name']
        address = location['address']['line1']
        city = location['address']['city']
        state = location['address']['state']
        zipcode = location['address']['zip']
        self.message += f'\n\n{name}\n{address}\n{city}, {state} {zipcode}'

    def message_footer(self):
        cst = pytz.timezone('US/Central')
        dt = datetime.now(cst)
        timestamp = dt.strftime('%b %d, %Y at %I:%M:%S %p')

        self.message += '\n\nRegister Here: https://www.hy-vee.com/my-pharmacy/covid-vaccine-consent'
        self.message += f'\nPosted {timestamp} CST'

    @tasks.loop(seconds=30)
    async def check_for_vaccine_availability_task(self):
        for config in configs:
            enabled = config['enabled'] if 'enabled' in config else True

            if enabled:
                if config['latitude'] and config['longitude'] and config['radius']:
                    test = config['test'] if 'test' in config else False
                    self.get_vaccine_availability(config['latitude'], config['longitude'], config['radius'])
                    self.get_newly_available_locations(test)
                else:
                    print('invalid config: missing geolocation data')

                if len(self.newly_available):
                    print(f'{len(self.newly_available)} newly available location(s) found')
                    self.message_start()
                    for location in self.newly_available:
                        self.message_location(location)
                    self.message_footer()

                    if config['channel']:
                        channel = self.get_channel(config['channel'])
                        print('sending notification to channel: ({channel})'.format(channel=config['channel']))
                        await channel.send(self.message)
                    else:
                        print('invalid config: missing discord channel')

    @check_for_vaccine_availability_task.before_loop
    async def before_my_task(self):
        await self.wait_until_ready()


# Start the bot
client = CovidVaccineBot()
client.run(os.getenv('DISCORD_BOT_TOKEN'))
