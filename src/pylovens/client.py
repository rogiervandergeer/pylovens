from base64 import b64encode, urlsafe_b64encode
from datetime import datetime
from hashlib import sha256
from json import dumps
from os import urandom
from re import sub
from typing import Iterable
from urllib.parse import quote

from requests import get, post

from pylovens._version import __version_tuple__


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
