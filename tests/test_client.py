from datetime import date, datetime, timedelta, timezone
from itertools import islice
from os import environ
from zoneinfo import ZoneInfo

from pytest import fixture, mark, raises, skip
from requests import HTTPError

from pylovens import LovensClient
from pylovens.exceptions import AuthenticationError, InvalidTokenError


class TestHeaders:
    def test_user_agent(self, client: LovensClient):
        headers = client._headers
        assert headers["User-Agent"].startswith("pylovens ")
        assert len(headers["User-Agent"].split(".")) in (3, 4)  # Either pylovens x.y.z or pylovens x.y.z.dev0
        assert "+" not in headers["User-Agent"]

    def test_headers_with_auth_without_token(self, client: LovensClient, mocker):
        mock = mocker.patch("pylovens.client.LovensClient._login")
        mock.return_value = ("token", datetime.now(tz=timezone.utc))
        client._access_token = None
        _ = client._headers_with_auth
        mock.assert_called_once()

    def test_headers_with_auth(self, client: LovensClient):
        client._access_token = ("token", datetime.now(tz=timezone.utc) + timedelta(hours=1))
        headers = client._headers_with_auth
        assert headers["Authorization"] == "Bearer token"

    def test_token_expired(self, client: LovensClient, mocker):
        mock = mocker.patch("pylovens.client.LovensClient._login")
        client._access_token = ("token", datetime.now(tz=timezone.utc) - timedelta(hours=1))
        _ = client._headers_with_auth
        mock.assert_called_once()


class TestLogin:
    def test_login_settings(self, client: LovensClient):
        assert client._login_settings_ is None
        settings = client._login_settings
        for key in ("idp_client_id", "idp_issuer_id", "login_page_allowed_redirect_uris", "idp_redirect_uri"):
            assert key in settings
        assert client._login_settings_ is not None

    def test_aws_cognito_client_id(self, client: LovensClient):
        client_id = client._get_aws_cognito_client_id()
        assert len(client_id) > 0

    def test_get_aws_cognito_token(self, client: LovensClient):
        try:
            token = client._get_aws_cognito_token(
                username=environ["LOVENS_USERNAME"], password=environ["LOVENS_PASSWORD"]
            )
            assert len(token) > 0
        except KeyError:
            skip("Requires authentication.")

    def test_invalid_credentials(self, client: LovensClient):
        with raises(AuthenticationError):
            client._get_aws_cognito_token(username="test", password="user")

    @mark.parametrize("token", ["invalid_token", "at_i1yelzysa43u749it8nv9p7ceub73"])
    def test_invalid_token(self, client: LovensClient, token: str):
        client._access_token = (token, datetime.now(tz=timezone.utc) + timedelta(hours=1))
        with raises(InvalidTokenError):
            client.get_bikes()
        assert client.access_token is None


class TestNormalizeDates:
    @fixture(scope="function")
    def client_with_timezone(self, client: LovensClient) -> LovensClient:
        client._timezone = "Europe/Amsterdam"
        return client

    @mark.parametrize(
        "start_date,end_date",
        [
            (None, None),
            (None, datetime(2023, 1, 1, tzinfo=ZoneInfo("Europe/Amsterdam"))),
            (datetime(2023, 1, 1, tzinfo=ZoneInfo("Europe/Amsterdam")), None),
            (
                datetime(2023, 1, 1, tzinfo=ZoneInfo("Europe/Amsterdam")),
                datetime(2023, 1, 2, tzinfo=ZoneInfo("Europe/Amsterdam")),
            ),
        ],
    )
    def test_passthrough(self, client_with_timezone: LovensClient, start_date, end_date):
        x, y = client_with_timezone._normalise_dates(start_date, end_date)
        assert x == start_date
        assert y == end_date

    def test_date_to_datetime(self, client_with_timezone: LovensClient):
        x, y = client_with_timezone._normalise_dates(date(2023, 1, 15), date(2023, 1, 30))
        assert x == datetime(2023, 1, 15, tzinfo=ZoneInfo("Europe/Amsterdam"))
        assert y == datetime(2023, 1, 30, 23, 59, 59, tzinfo=ZoneInfo("Europe/Amsterdam"))

    def test_tz_unaware(self, client_with_timezone: LovensClient):
        x, y = client_with_timezone._normalise_dates(
            datetime(2023, 1, 15), datetime(2023, 1, 30, tzinfo=ZoneInfo("Asia/Singapore"))
        )
        assert x == datetime(2023, 1, 15, tzinfo=ZoneInfo("Europe/Amsterdam"))
        assert y == datetime(2023, 1, 30, tzinfo=ZoneInfo("Asia/Singapore"))


class TestBattery:
    def test_get_battery_state(self, authenticated_client: LovensClient, bike_id: int):
        state = authenticated_client.get_battery_state(bike_id)
        assert "battery_percentage" in state

    def test_get_battery_statistics(self, authenticated_client: LovensClient, bike_id: int):
        stats = authenticated_client.get_battery_statistics(bike_id)
        seconds = (max(map(lambda x: x["date"], stats)) - min(map(lambda x: x["date"], stats))).total_seconds()
        assert 85400 <= seconds <= 87400  # Assert we have 24 hours +- 15 minutes

    def test_statistics_no_end_date(self, authenticated_client: LovensClient, bike_id: int):
        stats = authenticated_client.get_battery_statistics(bike_id, start_date=datetime.now() - timedelta(hours=3))
        assert 10 <= len(stats) <= 14

    def test_statistics_start_date_after_end_date(self, authenticated_client: LovensClient, bike_id: int):
        with raises(HTTPError):
            authenticated_client.get_battery_statistics(
                bike_id, start_date=datetime.now() - timedelta(hours=3), end_date=datetime.now() - timedelta(hours=5)
            )


class TestRides:
    def test_iterate_rides(self, authenticated_client: LovensClient, bike_id: int):
        rides = authenticated_client.iterate_rides(bike_id)
        for ride in rides:
            assert isinstance(ride, dict)
            assert isinstance(ride["creation_date"], datetime)
            break

    def test_offset(self, authenticated_client: LovensClient, bike_id: int):
        rides = islice(authenticated_client.iterate_rides(bike_id, batch_size=2), 3)
        assert len({ride["id"] for ride in rides}) == 3

    @mark.parametrize("newest_first", [False, True])
    def test_newest_first(self, authenticated_client: LovensClient, bike_id: int, newest_first: bool):
        rides = authenticated_client.get_rides(bike_id, n=2, newest_first=newest_first)
        assert (rides[0]["creation_date"] > rides[1]["creation_date"]) == newest_first

    def test_get_location(self, authenticated_client: LovensClient, ride: dict):
        locations = authenticated_client.get_location(
            bike_id=ride["bike_id"], start_date=ride["start_date"], end_date=ride["end_date"]
        )
        for location in locations:
            assert isinstance(location["date"], datetime)
            assert location["date"] >= locations[0]["date"]

    def test_get_ride(self, authenticated_client: LovensClient, ride: dict):
        ride_ = authenticated_client.get_ride(ride["id"])
        assert ride_ == ride


class TestMisc:
    def test_user(self, authenticated_client: LovensClient):
        user = authenticated_client.get_user()
        assert "timezone" in user
        assert "username" in user

    def test_timezone(self, authenticated_client: LovensClient):
        # Timezone in the format 'Europe/Amsterdam'
        assert isinstance(authenticated_client.timezone, ZoneInfo)

    def test_get_bikes(self, authenticated_client: LovensClient):
        bikes = authenticated_client.get_bikes()
        assert len(bikes) > 0
        assert bikes[0] == authenticated_client.get_bike(bikes[0]["id"])

    def test_get_state(self, authenticated_client: LovensClient, bike_id: int):
        state = authenticated_client.get_state(bike_id)
        assert "powered_on" in state
        assert isinstance(state["last_full_charge"], datetime)

    def test_get_health(self, authenticated_client: LovensClient, bike_id: int):
        health = authenticated_client.get_health(bike_id)
        assert isinstance(health[0]["value"], datetime)
        assert isinstance(health[1]["value"], datetime)
        assert isinstance(health[2]["value"], str)
        assert isinstance(health[3]["value"], str)


class TestGeofences:
    @fixture(scope="class")
    def geofence(self, authenticated_client: LovensClient, bike_id: int) -> dict:
        geofence_data = authenticated_client.get_geofences(bike_id)
        if len(geofence_data) == 0:
            skip("No geofences defined.")
        return geofence_data[0]

    def test_get_geofences(self, authenticated_client: LovensClient, geofence: dict):
        assert isinstance(geofence["creation_date"], datetime)

    def test_get_geofence_by_id(self, authenticated_client: LovensClient, geofence: dict):
        geofence_by_id = authenticated_client.get_geofence(geofence["id"])
        assert geofence_by_id == geofence

    def test_get_all_time_geofence_stats(self, authenticated_client: LovensClient, geofence: dict):
        geofence_stats = authenticated_client.get_geofence_stats(geofence["id"])
        assert len(geofence_stats) == 1
        assert "entries_all_time" in geofence_stats

    def test_get_geofence_stats(self, authenticated_client: LovensClient, geofence: dict):
        geofence_stats = authenticated_client.get_geofence_stats(
            geofence["id"], geofence["creation_date"], geofence["creation_date"] + timedelta(days=7)
        )
        assert geofence_stats.keys() == {"entries_all_time", "entries_in_timespan"}


class TestStatistics:
    def test_get_daily_statistics(self, authenticated_client: LovensClient, bike_id: int):
        stats = authenticated_client.get_statistics(bike_id, start_date=date(2023, 4, 1), end_date=date(2023, 4, 5))
        assert len(stats) == 5  # There are 5 days in the range.
        assert stats[0]["from"] == datetime(2023, 4, 1, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        assert stats[-1]["till"] == datetime(2023, 4, 5, 23, 59, 59, tzinfo=ZoneInfo("Europe/Amsterdam"))

    def test_get_hourly_statistics(self, authenticated_client: LovensClient, bike_id: int):
        stats = authenticated_client.get_statistics(
            bike_id, start_date=date(2023, 4, 1), end_date=date(2023, 4, 5), type="hourly"
        )
        assert len(stats) == 5 * 24  # There are 5 days * 24 hours in the range.
        assert stats[0]["from"] == datetime(2023, 4, 1, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        assert stats[-1]["till"] == datetime(2023, 4, 5, 23, 59, 59, tzinfo=ZoneInfo("Europe/Amsterdam"))

    def test_get_monthly_statistics(self, authenticated_client: LovensClient, bike_id: int):
        stats = authenticated_client.get_statistics(
            bike_id, start_date=date(2023, 4, 1), end_date=date(2023, 4, 5), type="monthly"
        )
        assert len(stats) == 1  # The range falls in one month.
        assert stats[0]["from"] == datetime(2023, 4, 1, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        assert stats[-1]["till"] == datetime(2023, 4, 5, 23, 59, 59, tzinfo=ZoneInfo("Europe/Amsterdam"))

    def test_stats_date_tz(self, authenticated_client: LovensClient, bike_id: int):
        authenticated_client._timezone = "Asia/Singapore"
        stats = authenticated_client.get_statistics(bike_id, start_date=date(2023, 4, 1), end_date=date(2023, 4, 5))
        authenticated_client._timezone = None
        assert len(stats) == 5  # There are 5 days in the range.
        assert stats[0]["from"] == datetime(2023, 4, 1, 0, 0, tzinfo=ZoneInfo("Asia/Singapore"))
        assert stats[-1]["till"] == datetime(2023, 4, 5, 23, 59, 59, tzinfo=ZoneInfo("Asia/Singapore"))

    def test_stats_datetime_naive(self, authenticated_client: LovensClient, bike_id: int):
        stats = authenticated_client.get_statistics(
            bike_id, start_date=datetime(2023, 4, 1, 0, 0), end_date=datetime(2023, 4, 1, 12, 59, 59), type="hourly"
        )
        assert len(stats) == 13
        assert stats[0]["from"] == datetime(2023, 4, 1, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        assert stats[-1]["till"] == datetime(2023, 4, 1, 12, 59, 59, tzinfo=ZoneInfo("Europe/Amsterdam"))

    def test_stats_datetime_tz(self, authenticated_client: LovensClient, bike_id: int):
        stats = authenticated_client.get_statistics(
            bike_id,
            start_date=datetime(2023, 4, 1, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam")),
            end_date=datetime(2023, 4, 1, 12, 59, 59, tzinfo=ZoneInfo("Europe/Amsterdam")),
            type="hourly",
        )
        assert len(stats) == 13
        assert stats[0]["from"] == datetime(2023, 4, 1, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        assert stats[-1]["till"] == datetime(2023, 4, 1, 12, 59, 59, tzinfo=ZoneInfo("Europe/Amsterdam"))

    def test_stats_datetime_partial(self, authenticated_client: LovensClient, bike_id: int):
        stats = authenticated_client.get_statistics(
            bike_id,
            start_date=datetime(2023, 4, 1, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam")),
            end_date=datetime(2023, 4, 1, 12, 30, 0, tzinfo=ZoneInfo("Europe/Amsterdam")),
            type="hourly",
        )
        assert len(stats) == 13
        assert stats[0]["from"] == datetime(2023, 4, 1, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        assert stats[-1]["till"] == datetime(2023, 4, 1, 12, 30, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
