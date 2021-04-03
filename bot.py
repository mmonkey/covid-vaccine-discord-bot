import discord
import json
import os
import pytz
import requests
from datetime import datetime
from discord.ext import tasks
from dotenv import load_dotenv
from geopy import distance

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

        self.message = ''
        self.hyvee_locations = []
        self.hyvee_availability = {}
        self.newly_available_hyvee_appointments = []

        self.spotter_cache = {}
        self.spotter_locations = []
        self.spotter_availability = {}
        self.newly_available_spotter_appointments = []

        self.check_for_vaccine_availability_task.start()

    async def on_ready(self):
        print(f'Logged in as {self.user.name} ({self.user.id})')

    # Hy-Vee Pharmacies
    def get_hyvee_vaccine_availability(self, latitude, longitude, radius):
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
            self.hyvee_locations = list(map(lambda location: location['location'], json_data['data']['searchPharmaciesNearPoint']))

        else:
            print(f'Error getting vaccine availability: {response.text}')
            self.hyvee_locations = []

    def get_newly_available_hyvee_locations(self, is_test=False):
        self.newly_available_hyvee_appointments = []

        for location in self.hyvee_locations:
            prev_avail = self.hyvee_availability[location['locationId']] if location['locationId'] in self.hyvee_availability else False

            if location['isCovidVaccineAvailable'] and not prev_avail:
                self.newly_available_hyvee_appointments.append(location)

            if not len(self.newly_available_hyvee_appointments) and is_test:
                self.newly_available_hyvee_appointments.append(location)

            self.hyvee_availability[location['locationId']] = location['isCovidVaccineAvailable']

    def message_hyvee_location(self, location):
        name = location['nickname'] if location['nickname'] else location['name']
        address = location['address']['line1']
        city = location['address']['city']
        state = location['address']['state']
        zipcode = location['address']['zip']
        url = 'https://www.hy-vee.com/my-pharmacy/covid-vaccine-consent'
        self.message += f'\n\n{name}\n{address}\n{city}, {state} {zipcode}\n{url}'

    # Other Pharmacies - vaccinespotter.org API
    def get_spotter_api_vaccine_availability(self, latitude, longitude, radius, states):
        locations = []
        for state in states:
            if state not in self.spotter_cache:
                response = requests.get(f'https://www.vaccinespotter.org/api/v0/states/{state}.json')

                if response.status_code == 200:
                    json_data = json.loads(response.text)
                    self.spotter_cache[state] = list(
                        filter(lambda loc: loc['properties']['provider'] != 'hyvee', json_data['features'])
                    )
                else:
                    self.spotter_cache[state] = []

            locations.extend(self.spotter_cache[state])

        self.spotter_locations = []
        search_coordinates = (latitude, longitude)
        for location in locations:
            location_coordinates = (location['geometry']['coordinates'][1], location['geometry']['coordinates'][0])
            if distance.distance(search_coordinates, location_coordinates).miles <= radius:
                self.spotter_locations.append(location)

    def get_newly_available_spotter_locations(self, is_test=False):
        self.newly_available_spotter_appointments = []

        for location in self.spotter_locations:
            prev_avail = self.spotter_availability[location['properties']['id']] if location['properties']['id'] in self.spotter_availability else False

            if location['properties']['appointments_available'] and not prev_avail:
                self.newly_available_spotter_appointments.append(location)

            if not len(self.newly_available_spotter_appointments) and is_test:
                self.newly_available_spotter_appointments.append(location)

            self.spotter_availability[location['properties']['id']] = location['properties']['appointments_available']

    def message_spotter_location(self, location):
        name = '{name} {provider}'.format(
            name=location['properties']['name'],
            provider=location['properties']['provider_brand_name']
        )
        address = location['properties']['address']
        city = location['properties']['city']
        state = location['properties']['state']
        zipcode = location['properties']['postal_code']
        url = location['properties']['url']
        self.message += f'\n\n{name}\n{address}\n{city}, {state} {zipcode}\n{url}'

    # Messaging header/footer
    def message_header(self):
        self.message = '@everyone :syringe: appointments available!'

    def message_footer(self):
        cst = pytz.timezone('US/Central')
        dt = datetime.now(cst)
        timestamp = dt.strftime('%b %d, %Y at %I:%M:%S %p')

        self.message += f'\n\nPosted {timestamp} CST'

    @tasks.loop(seconds=30)
    async def check_for_vaccine_availability_task(self):
        for config in configs:
            enabled = config['enabled'] if 'enabled' in config else True

            if enabled:
                if config['latitude'] and config['longitude'] and config['radius']:
                    is_test = config['test'] if 'test' in config else False
                    self.get_hyvee_vaccine_availability(config['latitude'], config['longitude'], config['radius'])
                    self.get_newly_available_hyvee_locations(is_test)

                    # clear the spotter cache
                    self.spotter_cache = {}
                    states = config['states'] if 'states' in config else ['NE']
                    self.get_spotter_api_vaccine_availability(
                        config['latitude'],
                        config['longitude'],
                        config['radius'],
                        states)
                    self.get_newly_available_spotter_locations(is_test)
                else:
                    print('invalid config: missing geolocation data')

                if len(self.newly_available_hyvee_appointments) or len(self.newly_available_spotter_appointments):
                    print(f'{len(self.newly_available_hyvee_appointments)} newly available hy-vee location(s) found')
                    print(f'{len(self.newly_available_spotter_appointments)} newly available spotter location(s) found')

                    self.message_header()
                    for location in self.newly_available_hyvee_appointments:
                        self.message_hyvee_location(location)

                    for location in self.newly_available_spotter_appointments:
                        self.message_spotter_location(location)

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
