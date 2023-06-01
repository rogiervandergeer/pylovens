from base64 import b64encode, urlsafe_b64encode
from datetime import datetime, date, time
from hashlib import sha256
from json import dumps
from os import urandom
from re import sub
from typing import Iterable
from urllib.parse import quote
from zoneinfo import ZoneInfo

from requests import get, post

from pylovens._version import __version_tuple__
from pylovens.utils import parse_datetimes


class LovensClient:
    client_id: str = "7d5d1a2a-3f6e-45c6-9e9e-b0b5f224f8a5"
    client_secret: str = ""

    def __init__(self):
        self.access_token: str | None = None
        self._login_settings_: dict | None = None

    def get_bikes(self) -> list[dict]:
        response = get("https://lovens.api.bike.conneq.tech/bike", headers=self._headers_with_auth)
        response.raise_for_status()
        return response.json()

    def get_location(self, bike_id: int, start_date: datetime | str, end_date: datetime | str):
        response = get(
            f"https://lovens.api.bike.conneq.tech/bike/{bike_id}/location?"
            f"from={quote(start_date)}&till={quote(end_date)}",
            headers=self._headers_with_auth,
        )
        response.raise_for_status()
        return response.json()

    def get_rides(self, bike_id: int, batch_size: int = 50, offset: int = 0) -> Iterable[dict]:
        response = get(
            f"https://lovens.api.bike.conneq.tech/v2/bike/{bike_id}/ride?"
            f"limit={batch_size}&offset={offset}&order%5B%5D=start_date%3Bdesc",
            headers=self._headers_with_auth,
        )
        response.raise_for_status()
        data = response.json()
        yield from data["data"]
        if data["meta"]["total_records"] > data["meta"]["offset"] + data["meta"]["limit"]:
            yield from self.get_rides(bike_id=bike_id, batch_size=batch_size, offset=offset + batch_size)

    def get_statistics(
        self,
        bike_id: int,
        start_date: date | datetime,
        end_date: date | datetime,
        type: str = "daily",
        tz: ZoneInfo | str = "Europe/Amsterdam",
        parse_timestamps: bool = True,
    ) -> list[dict]:
        """Get ride statistics for a bike.

        If start_date and/or end_date is a date object, they are interpreted as the start and end of the day
        respectively. Timezone-naive datetime objects are converted to the timezone as passed to the tz argument.

        Note that this endpoint expects the end_date, if it is a datetime, to be one second before the start of the
        next bin. E.g. daily statistics for the month of January 2023 can be obtained by calling
            get_statistics(123, start_date=datetime(2023, 1, 1, 0, 0), end_date=datetime(2023, 1, 31, 23, 59, 59)).
        Passing datetime(2023, 2, 1, 0, 0) as end_date instead will return in an extra 0-second bin at the end.

        Args:
            bike_id: The ID of the bike.
            start_date: Start date or datetime.
            end_date: End date or datetime (inclusive).
            type: Aggregation level. One of "hourly", "daily" or "monthly". Defaults to "daily".
            tz: Timezone to aggregate in. Defaults to "Europe/Amsterdam".
            parse_timestamps: If True, parse resulting timestamps into datetime objects. Defaults to True.

        Returns:
            A list of dictionaries of the following form:
              {
                'from': datetime(2023, 4, 30, 0, 0, 0, tzinfo=ZoneInfo(key='Europe/Amsterdam'),
                'till': datetime(2023, 4, 30, 23, 59, 59, tzinfo=ZoneInfo(key='Europe/Amsterdam'),
                'c02': 2584,
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
        if isinstance(tz, str):
            tz = ZoneInfo(tz)
        if not isinstance(start_date, datetime):
            start_date = datetime.combine(start_date, time(0, 0, tzinfo=tz))
        elif start_date.tzinfo is None:
            start_date = start_date.astimezone(tz)
        if not isinstance(end_date, datetime):
            end_date = datetime.combine(end_date, time(23, 59, 59, tzinfo=tz))
        elif end_date.tzinfo is None:
            end_date = end_date.astimezone(tz)

        response = get(
            f"https://lovens.api.bike.conneq.tech/bike/{bike_id}/stats?"
            f"from={quote(start_date.strftime('%Y-%m-%dT%H:%M:%S%z'))}&"
            f"till={quote(end_date.strftime('%Y-%m-%dT%H:%M:%S%z'))}&"
            f"type={type}&tz={tz.key}",
            headers=self._headers_with_auth,
        )
        response.raise_for_status()
        if parse_timestamps:
            return [parse_datetimes(stat, keys={"from", "till"}, timezone=tz) for stat in response.json()]
        else:
            return response.json()

    def login(self, username: str, password: str) -> None:
        token = self._get_aws_cognito_token(username, password)
        challenge, verifier = self._create_code_challenge()
        challenge_result = self._send_code_challenge(challenge, token)
        self.access_token = self._get_access_token(code=challenge_result, verifier=verifier)

    @staticmethod
    def _create_code_challenge() -> tuple[str, str]:
        code_verifier = urlsafe_b64encode(urandom(40)).decode("utf-8")
        code_verifier = sub("[^a-zA-Z0-9]+", "", code_verifier)
        code_challenge = sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = urlsafe_b64encode(code_challenge).decode("utf-8")
        code_challenge = code_challenge.replace("=", "")
        return code_challenge, code_verifier

    @property
    def _login_settings(self) -> dict:
        if self._login_settings_ is None:
            response = get(
                f"https://api.ids.conneq.tech/client/{self.client_id}/setting/loginpage", headers=self._headers
            )
            response.raise_for_status()
            self._login_settings_ = response.json()
        return self._login_settings_

    def _get_aws_cognito_client_id(self) -> str:
        """Obtain the AWS Cognito client_id."""
        response = get(
            f"https://api.ids.conneq.tech/client/{self._login_settings['idp_client_id']}/setting/signinpage",
            headers=self._headers,
        )
        response.raise_for_status()
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
        response.raise_for_status()
        return response.json()["AuthenticationResult"]["AccessToken"]

    def _get_access_token(self, code: str, verifier: str) -> str:
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
        return response.json()["access_token"]

    def _send_code_challenge(self, code_challenge: str, cognito_token: str) -> str:
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
        return {"User-Agent": f"pylovens {'.'.join([str(v) for v in __version_tuple__[:-1]])}"}

    @property
    def _headers_with_auth(self) -> dict[str, str]:
        """The headers including authorization. Only possible when authenticated."""
        if self.access_token is None:
            raise ValueError("Not authenticated.")
        return {"Authorization": f"Bearer {self.access_token}", **self._headers}
