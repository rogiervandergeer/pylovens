from itertools import islice
from os import environ

from pytest import mark, raises

from pylovens import LovensClient


class TestHeaders:
    def test_user_agent(self, client: LovensClient):
        headers = client._headers
        assert headers["User-Agent"].startswith("pylovens ")
        assert len(headers["User-Agent"].split(".")) in (3, 4)  # Either pylovens x.y.z or pylovens x.y.z.dev0

    def test_headers_with_auth_without_token(self, client: LovensClient):
        with raises(ValueError):
            _ = client._headers_with_auth

    def test_headers_with_auth(self, client: LovensClient):
        client.access_token = "token"
        headers = client._headers_with_auth
        assert headers["Authorization"] == "Bearer token"


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

    @mark.skipif(
        "LOVENS_USERNAME" not in environ or "LOVENS_PASSWORD" not in environ, reason="Requires authentication."
    )
    def test_get_aws_cognito_token(self, client: LovensClient):
        token = client._get_aws_cognito_token(username=environ["LOVENS_USERNAME"], password=environ["LOVENS_PASSWORD"])
        assert len(token) > 0


@mark.skipif("LOVENS_USERNAME" not in environ or "LOVENS_PASSWORD" not in environ, reason="Requires authentication.")
class TestApi:
    def test_get_bikes(self, authenticated_client):
        bikes = authenticated_client.get_bikes()
        assert len(bikes) > 0

    def test_get_rides(self, authenticated_client):
        bikes = authenticated_client.get_bikes()
        bike_id = bikes[0]["id"]
        ride_iterable = authenticated_client.get_rides(bike_id, batch_size=6)
        rides = list(islice(ride_iterable, 10))
        assert len(rides) == 10

    def test_get_location(self, authenticated_client):
        bikes = authenticated_client.get_bikes()
        bike_id = bikes[0]["id"]
        for ride in authenticated_client.get_rides(bike_id, batch_size=2):
            locations = authenticated_client.get_location(
                bike_id=bike_id, start_date=ride["start_date"], end_date=ride["end_date"]
            )
            assert len(locations) > 0
            break
