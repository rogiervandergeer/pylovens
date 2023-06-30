# pylovens

Python client for the Lovens API.

![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/rogiervandergeer/pylovens/test.yaml) 
![PyPI](https://img.shields.io/pypi/v/pylovens)
![PyPI - License](https://img.shields.io/pypi/l/pylovens)
![PyPI - Downloads](https://img.shields.io/pypi/dm/pylovens) 

With `pylovens` you can access the data that is available in the Lovens app for bikes with a [GPS unit](https://lovensbikes.com/product/gps-unit/).

## Usage

Using the client is as simple as:
```python
from pylovens import LovensClient

client = LovensClient("your_username", "your_secret_password")

bikes = client.get_bikes()
```

_Note:_ only authentication with email/password is supported. 


## Methods

The `LovensClient` exposes the following methods:

 - [User](#user)
   - [`get_user`](#get_user---get-information-on-the-user)
 - [Bikes](#bikes)
   - [`get_bikes`](#get_bikes---fetch-all-bikes-accessible-to-your-user)
   - [`get_bike`](#get_bike---fetch-a-bike-by-its-id)
   - [`get_state`](#get_state---get-the-state-of-a-bike)
   - [`get_health`](#get_health---get-bike-health-status)
 - [Rides](#rides)
   - [`iterate_rides`](#iterate_rides---iterate-through-the-rides-of-a-bike)
   - [`get_rides`](#get_rides---fetch-a-list-of-rides-of-a-bike)
   - [`get_ride`](#get_ride---fetch-a-ride-by-its-id)
   - [`get_location`](#get_location---get-location-history-in-a-time-range)
 - [Battery](#battery)
   - [`get_battery_state`](#get_battery_state---get-the-state-of-the-battery-of-a-bike)
   - [`get_battery_statistics`](#get_battery_statistics---get-historical-state-of-the-battery-of-a-bike)
 - [Statistics](#statistics)
   - [`get_statistics`](#get_statistics---get-ride-statistics-for-a-bike)
 - [Geofences](#geofences)
   - [`get_geofences`](#get_geofences---fetch-all-geofences-associated-to-a-bike)
   - [`get_geofence`](#get_geofence---get-a-single-geofence-by-its-id)
   - [`get_geofence_stats`](#get_geofence_stats---get-statistics-of-a-geofence)

### User

#### `get_user` - Get information on the user.
```python
def get_user(self) -> dict
```

##### Returns
An extensive dictionary with details on the user, including the following keys and many more:
```python
{
    "id": 1234,
    "name": "Your Name",
    "creation_date": datetime(2023, 4, 30, 23, 59, 59, tzinfo=ZoneInfo(key='Europe/Amsterdam'),
    "email": "your@mail.address",
    "timezone": "Europe/Amsterdam",
    ...
}
```

### Bikes

#### `get_bikes` - Fetch all bikes accessible to your user.
```python
def get_bikes(self) -> list[dict]
```

##### Returns
A list of dictionaries of the following form:
```python
{
  'id': 456,
  'user_id': 1234,
  'user_name': 'Your Name',
  'active_state': 0,
  'name': 'Your Bikes Name',
  'last_location': { <most recent available result of the get_location method> },
  'battery_percentage': 50,
  'owning_user': { <result of get_user method> },
  'geofences': [ <result of get_geofences method> ],
  ...
}
```

#### `get_bike` - Fetch a bike by its ID.
```python
def get_bike(self, bike_id: int) -> dict
```

##### Arguments
- `bike_id`: The ID of the bike.

##### Returns
A dictionaries of the following form:
```python
{
  'id': 456,
  'user_id': 1234,
  'user_name': 'Your Name',
  'active_state': 0,
  'name': 'Your Bikes Name',
  'last_location': { <most recent available result of the get_location method> },
  'battery_percentage': 50,
  'owning_user': { <result of get_user method> },
  'geofences': [ <result of get_geofences method> ],
  ...
}
```

#### `get_state` - Get the state of a bike.
```python
def get_state(self, bike_id: int) -> dict[str]
```

##### Arguments
- `bike_id`: The ID of the bike.

##### Returns
A dictionary of the following form:
```python
{
  'powered_on': False,
  'ecu_locked': False,
  'erl_locked': False,
  'battery_percentage': 50,
  'charging': False,
  'last_full_charge': datetime(2023, 4, 1, 17, 10, 30, tzinfo=ZoneInfo(key='Europe/Amsterdam')),
  'odometer': 300,
  'range': 30
}
```

#### `get_health` - Get bike health status.
```python
def get_health(self, bike_id: int) -> list[dict]
```

##### Arguments
- `bike_id`: The ID of the bike.

##### Returns
A list of four dictionaries:
```python
[
  {
    'key': 'last_connection',
    'status': True,
    'value': datetime(2023, 4, 1, 17, 10, 30, tzinfo=ZoneInfo(key='Europe/Amsterdam')),
    'value_type': 'datetime'
  },
  {
    'key': 'last_gps',
    'status': False,
    'value': datetime(2023, 3, 31, 16, 51, 22, tzinfo=ZoneInfo(key='Europe/Amsterdam')),
    'value_type': 'datetime'
  },
  {
    'key': 'gps_battery',
    'status': True,
    'value': '75%',
    'value_type': 'string'
  },
  {
    'key': 'bike_system',
    'status': True,
    'value': 'true',
    'value_type': 'bool'
  }
]
```

### Rides

#### `iterate_rides` - Iterate through the rides of a bike.
```python
def iterate_rides(
        self, bike_id: int, newest_first: bool = True, batch_size: int = 50, _offset: int = 0
    ) -> Iterable[dict]
```

##### Arguments
- `bike_id`: The ID of the bike.
- `newest_first`: If True, fetch the most recent ride first. Defaults to `True`.
- `batch_size`: The number of rides to fetch at once.
- `_offset`: Used in pagination.

##### Returns
An iterable of dictionaries describing the rides.
Each dictionary contains, among others, the following keys:
```python
{
    "id": 123456,
    "start_date": datetime(2023, 4, 1, 17, 1, 0, tzinfo=ZoneInfo(key='Europe/Amsterdam')),
    "end_date": datetime(2023, 4, 1, 17, 6, 30, tzinfo=ZoneInfo(key='Europe/Amsterdam')),
    "calories": 14,
    "avg_speed": 21,
    "distance_traveled": 1234,
    "bike_id": 123,
    "user_id": 1234,
    "user": { <same as output of get_user()> },
    "creation_date": datetime(2023, 4, 1, 17, 10, 30, tzinfo=ZoneInfo(key='Europe/Amsterdam')),
    "active_time": 330,
    "timezone": "Europe/Amsterdam",
    ...
}
```

#### `get_rides` - Fetch a list of rides of a bike.
```python
def get_rides(self, bike_id: int, newest_first: bool = True, n: int = 50) -> list[dict]
```

If you are interested in fetching all rides of a bike, or are not sure how many you need,
consider using `iterate_rides`.

##### Arguments
- `bike_id`: The ID of the bike.
- `newest_first`: If True, fetch the most recent ride first. Defaults to True.
- `n`: Number of rides to fetch. Defaults to 50.

##### Returns
An list of dictionaries describing the rides.
Each dictionary contains, among others, the following keys:
```python
{
    "id": 123456,
    "start_date": datetime(2023, 4, 1, 17, 1, 0, tzinfo=ZoneInfo(key='Europe/Amsterdam')),
    "end_date": datetime(2023, 4, 1, 17, 6, 30, tzinfo=ZoneInfo(key='Europe/Amsterdam')),
    "calories": 14,
    "avg_speed": 21,
    "distance_traveled": 1234,
    "bike_id": 123,
    "user_id": 1234,
    "user": { <same as output of get_user()> },
    "creation_date": datetime(2023, 4, 1, 17, 10, 30, tzinfo=ZoneInfo(key='Europe/Amsterdam')),
    "active_time": 330,
    "timezone": "Europe/Amsterdam",
    ...
}
```

#### `get_ride` - Fetch a ride by its ID.
```python
def get_ride(self, ride_id: int) -> dict
```

##### Arguments
- `ride_id`: The ID of the ride.

##### Returns
A dictionary describing the ride.
It contains, among others, the following keys:
```python
{
    "id": 123456,
    "start_date": datetime(2023, 4, 1, 17, 1, 0, tzinfo=ZoneInfo(key='Europe/Amsterdam')),
    "end_date": datetime(2023, 4, 1, 17, 6, 30, tzinfo=ZoneInfo(key='Europe/Amsterdam')),
    "calories": 14,
    "avg_speed": 21,
    "distance_traveled": 1234,
    "bike_id": 123,
    "user_id": 1234,
    "user": { <same as output of get_user()> },
    "creation_date": datetime(2023, 4, 1, 17, 10, 30, tzinfo=ZoneInfo(key='Europe/Amsterdam')),
    "active_time": 330,
    "timezone": "Europe/Amsterdam",
    ...
}
```

#### `get_location` - Get location history in a time range.
```python
def get_location(
        self, bike_id: int, start_date: datetime | date, end_date: datetime | date
    ) -> list[dict, bool, datetime | int | float]
```
If `start_date` and/or `end_date` is a date object, they are interpreted as the start and end of the day
respectively. Timezone-naive datetime objects are converted to the user's timezone (see `get_user`).

##### Arguments
- `bike_id`: The ID of the bike.
- `start_date`: Start date of a timespan.
- `end_date`: End date of a timespan.

##### Returns
A list of dictionaries of the following form:
```python
{
    "id": "123456b123",
    'lat': 52.379189,
    'lon': 4.899431,
    "date": datetime(2023, 4, 1, 17, 1, 0, tzinfo=ZoneInfo(key='Europe/Amsterdam')),
    "speed": 21,
    "battery_percentage": 0,  # Always 0 - never filled
    "bike_id": 123,
    "is_moving": True
}
```

### Battery

#### `get_battery_state` - Get the state of the battery of a bike.
```python
def get_battery_state(self, bike_id: int) -> dict[str]
```

##### Arguments
- `bike_id`: The ID of the bike.

##### Returns
A dictionary of the following form:
```python
{
  'current': -450,
  'battery_percentage': 69,
  'last_battery_update': datetime(2023, 4, 30, 0, 0, 0, tzinfo=ZoneInfo(key='Europe/Amsterdam'),
  'last_full_charge': datetime(2023, 4, 30, 0, 0, 0, tzinfo=ZoneInfo(key='Europe/Amsterdam'),
  'charging': False,
  'range': 30
}
```

#### `get_battery_statistics` - Get historical state of the battery of a bike.
```python
def get_battery_statistics(
        self,
        bike_id: int,
        start_date: date | datetime | None = None,
        end_date: date | datetime | None = None,
    )
```
If start_date is not provided or None, it defaults to 24 hours ago.
If end_date is not provided or None, it defaults to now.

If `start_date` and/or `end_date` is a date object, they are interpreted as the start and end of the day
respectively. Timezone-naive datetime objects are converted to the user's timezone (see `get_user`).

##### Arguments
- `bike_id`: The ID of the bike.
- `start_date`: Optional start date or datetime.
- `end_date`: Optional end date or datetime (inclusive).

##### Returns
A list of dictionaries of the following form, in 15-minute intervals:
```python
  {
    'date': datetime(2023, 4, 30, 0, 0, 0, tzinfo=ZoneInfo(key='Europe/Amsterdam'),
    'battery_percentage': 69,
    'charging': False,
    'seconds_in_ride': 0,
    'seconds_charging': 0,
  }
```

Note that `battery_percentage` is `None` when the battery is removed.

### Statistics

#### `get_statistics` - Get ride statistics for a bike.
```python
def get_statistics(
        self,
        bike_id: int,
        start_date: date | datetime,
        end_date: date | datetime,
        type: str = "daily",
    ) -> list[dict]
```
If `start_date` and/or `end_date` is a date object, they are interpreted as the start and end of the day
respectively. Timezone-naive datetime objects are converted to the user's timezone (see `get_user`).

Note that this endpoint expects the `end_date`, if it is a datetime, to be one second before the start of the
next bin. E.g. daily statistics for the month of January 2023 can be obtained by calling
    `get_statistics(123, start_date=datetime(2023, 1, 1, 0, 0), end_date=datetime(2023, 1, 31, 23, 59, 59))`.
Passing `datetime(2023, 2, 1, 0, 0)` as `end_date` instead will return in an extra 0-second bin at the end.

##### Arguments
- `bike_id`: The ID of the bike.
- `start_date`: Start date or datetime.
- `end_date`: End date or datetime (inclusive).
- `type`: Aggregation level. One of "hourly", "daily" or "monthly". Defaults to "daily".

##### Returns
A list of dictionaries of the following form:
```python
{
  'from': datetime(2023, 4, 30, 0, 0, 0, tzinfo=ZoneInfo(key='Europe/Amsterdam'),
  'till': datetime(2023, 4, 30, 23, 59, 59, tzinfo=ZoneInfo(key='Europe/Amsterdam'),
  'co2': 2584,
  'calories': 156,
  'avg_speed': 18,
  'distance_traveled': 10379,
  'avg_power_distribution': 83,
  'shift_advice': 0,
  'top_speed': 28,
  'elevation_up': 238,
  'elevation_down': 232
}
```


### Geofences

#### `get_geofences` - Fetch all geofences associated to a bike.
```python
def get_geofences(self, bike_id: int) -> list[dict[str, datetime | dict[str, float] | int | str]]
```

##### Arguments
- `bike_id`: The ID of the bike.

##### Returns
A list of dictionaries of the following form:
```python
{
  'id': 456,
  'bike_id': 123,
  'user_id': 1234,
  'name': 'Amsterdam City Center',
  'center': {'lat': 52.379189, 'lon': 4.899431},
  'radius': 200,
  'active_state': 0,
  'creation_date': datetime(2023, 4, 1, 17, 10, 30, tzinfo=ZoneInfo(key='Europe/Amsterdam'))
}
```

#### `get_geofence` - Get a single geofence by its ID.
```python
def get_geofence(self, geofence_id: int) -> dict[str, datetime | dict[str, float] | int | str]
```

##### Arguments
- `geofence_id`: The ID of the geofence.

##### Returns
A dictionary of the following form:
```python
{
  'id': 456,
  'bike_id': 123,
  'user_id': 1234,
  'name': 'Amsterdam City Center',
  'center': {'lat': 52.379189, 'lon': 4.899431},
  'radius': 200,
  'active_state': 0,
  'creation_date': datetime(2023, 4, 1, 17, 10, 30, tzinfo=ZoneInfo(key='Europe/Amsterdam'))
}
```

#### `get_geofence_stats` - Get statistics of a geofence.
```python
def get_geofence_stats(
        self,
        geofence_id: int,
        start_date: datetime | date | None = None,
        end_date: datetime | date | None = None,
    ) -> dict[str, int]
```

##### Arguments
- `geofence_id`: The ID of the geofence.
- `start_date`: Start date of a timespan. Optional, must be provided if `end_date` is provided.
- `end_date`: End date of a timespan. Optional, must be provided if `start_date` is provided.

##### Returns
A dictionary of the following form:
```python
{
  'entries_all_time': 1,
  'entries_in_timespan': 0  # Only if start_date and end_date provided.
}
```
