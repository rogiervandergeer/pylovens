from base64 import b64encode, urlsafe_b64encode
from datetime import datetime, date, time, timezone
from functools import partial
from hashlib import sha256
from itertools import islice
from json import dumps
from os import urandom
from re import sub
from typing import Iterable
from urllib.parse import quote
from zoneinfo import ZoneInfo

from requests import Response, get, post

from pylovens._version import __version__
from pylovens.exceptions import AuthenticationError, InvalidTokenError


class LovensClient:
    client_id: str = "7d5d1a2a-3f6e-45c6-9e9e-b0b5f224f8a5"
    client_secret: str = ""

    def __init__(self, username: str, password: str):
        self.credentials: tuple[str, str] = (username, password)
        self._access_token: tuple[str, datetime] | None = None
        self._login_settings_: dict | None = None
        self._timezone: str | None = None

    def get_battery_state(self, bike_id: int) -> dict[str]:
        """
        Get the state of the battery of a bike.

        Args:
            bike_id: The ID of the bike.

        Returns:
            A dictionary of the following form:
              {
                'current': -450,
                'battery_percentage': 69,
                'last_battery_update': datetime(2023, 4, 30, 0, 0, 0, tzinfo=ZoneInfo(key='Europe/Amsterdam'),
                'last_full_charge': datetime(2023, 4, 30, 0, 0, 0, tzinfo=ZoneInfo(key='Europe/Amsterdam'),
                'charging': False,
                'range': 30
              }
        """
        response = get(
            f"https://lovens.api.bike.conneq.tech/bike/{bike_id}/battery/current-state", headers=self._headers_with_auth
        )
        self._handle_errors(response)
        return self._parse_dates(response.json(), keys={"last_battery_update", "last_full_charge"})

    def get_battery_statistics(
        self,
        bike_id: int,
        start_date: date | datetime | None = None,
        end_date: date | datetime | None = None,
    ):
        """
        Get historical state of the battery of a bike.

        If start_date is not provided or None, it defaults to 24 hours ago.
        If end_date is not provided or None, it defaults to now.

        If start_date and/or end_date is a date object, they are interpreted as the start and end of the day
        respectively. Timezone-naive datetime objects are converted to the user's timezone (see get_user).

        Args:
            bike_id: The ID of the bike.
            start_date: Optional start date or datetime.
            end_date: Optional end date or datetime (inclusive).

        Returns:
            A list of dictionaries of the following form, in 15-minute intervals:
              {
                'date': datetime(2023, 4, 30, 0, 0, 0, tzinfo=ZoneInfo(key='Europe/Amsterdam'),
                'battery_percentage': 69,
                'charging': False,
                'seconds_in_ride': 0,
                'seconds_charging': 0,
              }

            Note that 'battery_percentage' is None when the bike is turned off.
        """
        if start_date is not None:
            if not isinstance(start_date, datetime):
                start_date = datetime.combine(start_date, time(0, 0, tzinfo=self.timezone))
            elif start_date.tzinfo is None:
                start_date = start_date.astimezone(self.timezone)
        if end_date is not None:
            if not isinstance(end_date, datetime):
                end_date = datetime.combine(end_date, time(23, 59, 59, tzinfo=self.timezone))
            elif end_date.tzinfo is None:
                end_date = end_date.astimezone(self.timezone)

        url = f"https://lovens.api.bike.conneq.tech/bike/{bike_id}/battery?"
        if start_date is not None:
            url += f"from={quote(start_date.strftime('%Y-%m-%dT%H:%M:%S%z'))}"
            if end_date is not None:
                url += "&"
        if end_date is not None:
            url += f"till={quote(end_date.strftime('%Y-%m-%dT%H:%M:%S%z'))}"

        response = get(url, headers=self._headers_with_auth)
        self._handle_errors(response)
        return list(map(self._parse_dates, response.json()))

    def get_bike(self, bike_id: int) -> dict:
        """
        Fetch a bike by its ID.

        Args:
            bike_id: The ID of the bike.

        Returns:
            A dictionaries of the following form:
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
        """
        response = get(f"https://lovens.api.bike.conneq.tech/bike/{bike_id}", headers=self._headers_with_auth)
        self._handle_errors(response)
        return self._parse_dates(response.json())

    def get_bikes(self) -> list[dict]:
        """
        Fetch all bikes accessible to your user.

        Returns:
            A list of dictionaries of the following form:
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
        """
        response = get("https://lovens.api.bike.conneq.tech/bike", headers=self._headers_with_auth)
        self._handle_errors(response)
        return list(map(self._parse_dates, response.json()))

    def get_geofences(self, bike_id: int) -> list[dict[str, datetime | dict[str, float] | int | str]]:
        """
        Fetch all geofences associated to a bike.

        Args:
            bike_id: The ID of the bike.

        Returns:
            A list of dictionaries of the following form:
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
        """
        response = get(f"https://lovens.api.bike.conneq.tech/bike/{bike_id}/geofence", headers=self._headers_with_auth)
        self._handle_errors(response)
        return [self._parse_dates(geofence) for geofence in response.json()]

    def get_geofence(self, geofence_id: int) -> dict[str, datetime | dict[str, float] | int | str]:
        """
        Get a single geofence by its ID.

        Args:
            geofence_id: The ID of the geofence.

        Returns:
            A dictionary of the following form:
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
        """
        response = get(
            f"https://lovens.api.bike.conneq.tech/bike/geofence/{geofence_id}", headers=self._headers_with_auth
        )
        self._handle_errors(response)
        return self._parse_dates(response.json())

    def get_geofence_stats(
        self,
        geofence_id: int,
        start_date: datetime | date | None = None,
        end_date: datetime | date | None = None,
    ) -> dict[str, int]:
        """
        Get statistics of a geofence.

        Args:
            geofence_id: The ID of the geofence.
            start_date: Start date of a timespan. Optional, must be provided if end_date is provided.
            end_date: End date of a timespan. Optional, must be provided if start_date is provided.

        Returns:
            A dictionary of the following form:
              {
                'entries_all_time': 1,
                'entries_in_timespan': 0  # Only if start_date and end_date provided.
              }
        """
        if (start_date is None) != (end_date is None):
            raise ValueError("Either start_date and end_date must both be None, or both be provided.")
        start_date, end_date = self._normalise_dates(start_date, end_date)

        url = f"https://lovens.api.bike.conneq.tech/bike/geofence/{geofence_id}/stats"
        if start_date is not None:
            url += (
                f"?from={quote(start_date.strftime('%Y-%m-%dT%H:%M:%S%z'))}&"
                f"till={quote(end_date.strftime('%Y-%m-%dT%H:%M:%S%z'))}"
            )

        response = get(url, headers=self._headers_with_auth)
        self._handle_errors(response)
        return response.json()

    def get_health(self, bike_id: int) -> list[dict]:
        """
        Get bike health status.

        Args:
            bike_id: The ID of the bike.

        Returns:
            A list of four dictionaries:
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
        """
        response = get(f"https://lovens.api.bike.conneq.tech/bike/{bike_id}/health", headers=self._headers_with_auth)
        self._handle_errors(response)
        return [self._parse_dates(d, keys={"value"}) if d["value_type"] == "datetime" else d for d in response.json()]

    def get_location(
        self, bike_id: int, start_date: datetime | date, end_date: datetime | date
    ) -> list[dict, bool, datetime | int | float]:
        """
        Get location history in a time range.

        If start_date and/or end_date is a date object, they are interpreted as the start and end of the day
        respectively. Timezone-naive datetime objects are converted to the user's timezone (see get_user).

        Args:
            bike_id: The ID of the bike.
            start_date: Start date of a timespan.
            end_date: End date of a timespan.

        Returns:
            A list of dictionaries of the following form:
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
        """
        start_date, end_date = self._normalise_dates(start_date, end_date)

        response = get(
            f"https://lovens.api.bike.conneq.tech/bike/{bike_id}/location?"
            f"from={quote(start_date.strftime('%Y-%m-%dT%H:%M:%S%z'))}&"
            f"till={quote(end_date.strftime('%Y-%m-%dT%H:%M:%S%z'))}",
            headers=self._headers_with_auth,
        )
        self._handle_errors(response)
        return list(sorted(map(self._parse_dates, response.json()), key=lambda d: d["date"]))

    def get_ride(self, ride_id: int) -> dict:
        """
        Fetch a ride by its ID.

        Args:
            ride_id: The ID of the ride.

        Returns:
            A dictionary describing the ride.
            It contains, among others, the following keys:
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
        """
        response = get(f"https://lovens.api.bike.conneq.tech/v2/bike/ride/{ride_id}", headers=self._headers_with_auth)
        self._handle_errors(response)
        return self._parse_dates(response.json())

    def get_rides(self, bike_id: int, newest_first: bool = True, n: int = 50) -> list[dict]:
        """
        Fetch a list of rides of a bike.

        If you are interested in fetching all rides of a bike, or are not sure how many you need,
        consider using iterate_rides.

        Args:
            bike_id: The ID of the bike.
            newest_first: If True, fetch the most recent ride first. Defaults to True.
            n: Number of rides to fetch. Defaults to 50.

        Returns:
            An list of dictionaries describing the rides.
            Each dictionary contains, among others, the following keys:
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
        """
        return list(islice(self.iterate_rides(bike_id=bike_id, newest_first=newest_first), n))

    def iterate_rides(
        self, bike_id: int, newest_first: bool = True, batch_size: int = 50, _offset: int = 0
    ) -> Iterable[dict]:
        """
        Iterate through the rides of a bike.

        Args:
            bike_id: The ID of the bike.
            newest_first: If True, fetch the most recent ride first. Defaults to True.
            batch_size: The number of rides to fetch at once.
            _offset: Used in pagination.

        Returns:
            An iterable of dictionaries describing the rides.
            Each dictionary contains, among others, the following keys:
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
        """
        response = get(
            f"https://lovens.api.bike.conneq.tech/v2/bike/{bike_id}/ride?"
            f"limit={batch_size}&"
            f"offset={_offset}&"
            f"order%5B%5D=start_date%3B{'desc' if newest_first else 'asc'}",
            headers=self._headers_with_auth,
        )
        self._handle_errors(response)
        data = response.json()
        yield from map(self._parse_dates, data["data"])
        if data["meta"]["total_records"] > data["meta"]["offset"] + data["meta"]["limit"]:
            yield from self.iterate_rides(bike_id=bike_id, batch_size=batch_size, _offset=_offset + batch_size)

    def get_state(self, bike_id: int) -> dict[str]:
        """
        Get the state of a bike.

        Args:
            bike_id: The ID of the bike.

        Returns:
            A dictionary of the following form:
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
        """
        response = get(f"https://lovens.api.bike.conneq.tech/bike/{bike_id}/state", headers=self._headers_with_auth)
        self._handle_errors(response)
        return self._parse_dates(response.json()[0], keys={"last_full_charge"})

    def get_statistics(
        self,
        bike_id: int,
        start_date: date | datetime,
        end_date: date | datetime,
        type: str = "daily",
    ) -> list[dict]:
        """
        Get ride statistics for a bike.

        If start_date and/or end_date is a date object, they are interpreted as the start and end of the day
        respectively. Timezone-naive datetime objects are converted to the user's timezone (see get_user).

        Note that this endpoint expects the end_date, if it is a datetime, to be one second before the start of the
        next bin. E.g. daily statistics for the month of January 2023 can be obtained by calling
            get_statistics(123, start_date=datetime(2023, 1, 1, 0, 0), end_date=datetime(2023, 1, 31, 23, 59, 59)).
        Passing datetime(2023, 2, 1, 0, 0) as end_date instead will return in an extra 0-second bin at the end.

        Args:
            bike_id: The ID of the bike.
            start_date: Start date or datetime.
            end_date: End date or datetime (inclusive).
            type: Aggregation level. One of "hourly", "daily" or "monthly". Defaults to "daily".

        Returns:
            A list of dictionaries of the following form:
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
        """
        start_date, end_date = self._normalise_dates(start_date, end_date)

        response = get(
            f"https://lovens.api.bike.conneq.tech/bike/{bike_id}/stats?"
            f"from={quote(start_date.strftime('%Y-%m-%dT%H:%M:%S%z'))}&"
            f"till={quote(end_date.strftime('%Y-%m-%dT%H:%M:%S%z'))}&"
            f"type={type}&tz={self.timezone.key}",
            headers=self._headers_with_auth,
        )
        self._handle_errors(response)
        return list(map(partial(self._parse_dates, keys={"from", "till"}), response.json()))

    def get_user(self) -> dict:
        """
        Get information on the user.

        Returns:
            An extensive dictionary with details on the user, including the following keys and many more:
            {
                "id": 1234,
                "name": "Your Name",
                "creation_date": datetime(2023, 4, 30, 23, 59, 59, tzinfo=ZoneInfo(key='Europe/Amsterdam'),
                "email": "your@mail.address",
                "timezone": "Europe/Amsterdam",
                ...
            }
        """
        response = get(f"https://lovens.api.bike.conneq.tech/user/me", headers=self._headers_with_auth)
        self._handle_errors(response)
        data = response.json()
        self._timezone = data["timezone"]
        return self._parse_dates(data)

    @property
    def timezone(self) -> ZoneInfo:
        """The timezone of your user."""
        if self._timezone is None:
            self.get_user()
        return ZoneInfo(self._timezone)

    @staticmethod
    def _create_code_challenge() -> tuple[str, str]:
        code_verifier = urlsafe_b64encode(urandom(40)).decode("utf-8")
        code_verifier = sub("[^a-zA-Z0-9]+", "", code_verifier)
        code_challenge = sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = urlsafe_b64encode(code_challenge).decode("utf-8")
        code_challenge = code_challenge.replace("=", "")
        return code_challenge, code_verifier

    def _login(self) -> tuple[str, datetime]:
        """Log in using username (e-mail address) and password."""
        token = self._get_aws_cognito_token(*self.credentials)
        challenge, verifier = self._create_code_challenge()
        challenge_result = self._send_code_challenge(challenge, token)
        return self._get_access_token(code=challenge_result, verifier=verifier)

    @property
    def _login_settings(self) -> dict:
        """Return the login settings corresponding to our client ID."""
        if self._login_settings_ is None:
            response = get(
                f"https://api.ids.conneq.tech/client/{self.client_id}/setting/loginpage", headers=self._headers
            )
            self._handle_errors(response)
            self._login_settings_ = response.json()
        return self._login_settings_

    def _get_aws_cognito_client_id(self) -> str:
        """Obtain the AWS Cognito client_id."""
        response = get(
            f"https://api.ids.conneq.tech/client/{self._login_settings['idp_client_id']}/setting/signinpage",
            headers=self._headers,
        )
        self._handle_errors(response)
        return response.json()["cognito_config"]["aws_user_pools_web_client_id"]

    def _get_aws_cognito_token(self, username: str, password: str) -> str:
        """Authenticate with AWS Cognito and obtain an AccessToken"""
        response = post(
            self._login_settings["idp_issuer_id"],
            data=dumps(
                {
                    "AuthFlow": "USER_PASSWORD_AUTH",
                    "ClientId": self._get_aws_cognito_client_id(),
                    "AuthParameters": {"USERNAME": username, "PASSWORD": password},
                    "ClientMetadata": {},
                }
            ),
            headers={
                "Content-Type": "application/x-amz-json-1.1",
                "Referer": "https://login.conneq.tech/",
                "Origin": "https://login.conneq.tech",
                "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
                **self._headers,
            },
        )
        if response.status_code == 400:
            raise AuthenticationError()
        self._handle_errors(response)
        return response.json()["AuthenticationResult"]["AccessToken"]

    def _get_access_token(self, code: str, verifier: str) -> tuple[str, datetime]:
        """Sign in with Lovens using the previously obtained code and obtain the bearer token."""
        redirect_uri = self._login_settings["login_page_allowed_redirect_uris"][0]
        content = f"""code={code}&code_verifier={verifier}&redirect_uri={redirect_uri}&grant_type=authorization_code"""
        response = post(
            "https://api.ids.conneq.tech/oauth",
            data=content,
            headers={
                "Authorization": b"Basic " + b64encode(f"{self.client_id}:{self.client_secret}".encode("utf-8")),
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                **self._headers,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["access_token"], datetime.strptime(data["expires_at"][:-4] + "Z", "%Y-%m-%dT%H:%M:%S.%f%z")

    def _send_code_challenge(self, code_challenge: str, cognito_token: str) -> str:
        """Send a code challenge and the AWS Cognito token."""
        return post(
            "https://api.ids.conneq.tech/oauth",
            data=dumps(
                {
                    "client_id": self.client_id,
                    "issuer_id": self._login_settings["idp_issuer_id"],
                    "code": cognito_token,
                    "redirect_uri": self._login_settings["login_page_allowed_redirect_uris"][0],
                    "idp_redirect_uri": self._login_settings["idp_redirect_uri"],
                    "grant_type": "idp_authorization_code_idtoken",
                    "code_challenge": code_challenge,
                    "code_challenge_method": "S256",
                }
            ),
            headers={
                "Content-Type": "application/json",
                "Origin": "https://login.ids.conneq.tech",
                "Referer": "https://login.ids.conneq.tech/",
                **self._headers,
            },
        ).json()["code"]

    @property
    def _headers(self) -> dict[str, str]:
        """Get the HTTP headers to be sent with every request."""
        return {"User-Agent": f"pylovens {__version__.split('+')[0]}"}

    @property
    def _headers_with_auth(self) -> dict[str, str]:
        """The headers including authorization. Only possible when authenticated."""
        if self._access_token is None or self._access_token[1] < datetime.now(tz=timezone.utc):
            self._access_token = self._login()
        return {"Authorization": f"Bearer {self._access_token[0]}", **self._headers}

    def _parse_dates(self, data: dict[str], keys: set[str] | None = None) -> dict[str]:
        """Parse datetimes in a dictionary."""
        return {
            key: datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z").astimezone(self.timezone)
            if (keys is not None and key in keys) or (keys is None and (key.endswith("_date") or key == "date"))
            else value
            for key, value in data.items()
        }

    def _handle_errors(self, response: Response) -> None:
        """Check for error codes."""
        if response.status_code in (401, 403):  # 401 is returned for invalid tokens, 403 for malformed tokens
            self.access_token = None
            raise InvalidTokenError()
        response.raise_for_status()

    def _normalise_dates(
        self, start_date: datetime | date | None, end_date: datetime | date | None
    ) -> tuple[datetime | None, datetime | None]:
        """
        Normalise a date range input.

        If start_date and/or end_date is a date object, they are interpreted as the start and end of the day
        respectively. Timezone-naive datetime objects are converted to the user's timezone (see get_user).

        Nones are passed trough.

        Args:
            start_date: datetime, date or None
            end_date: datetime, date or None

        Returns:
            [datetime | None, datetime | None]
        """
        if start_date is None:
            pass
        elif not isinstance(start_date, datetime):  # start_date is a date
            start_date = datetime.combine(start_date, time(0, 0, tzinfo=self.timezone))
        elif start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=self.timezone)

        if end_date is None:
            pass
        elif not isinstance(end_date, datetime):
            end_date = datetime.combine(end_date, time(23, 59, 59, tzinfo=self.timezone))
        elif end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=self.timezone)

        return start_date, end_date
