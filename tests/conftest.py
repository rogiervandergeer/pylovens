from os import environ

from pytest import fixture, mark

from pylovens import LovensClient


@fixture(scope="function")
def client() -> LovensClient:
    return LovensClient()


@fixture(scope="session")
def authenticated_client() -> LovensClient:
    client = LovensClient()
    client.login(environ["LOVENS_USERNAME"], environ["LOVENS_PASSWORD"])
    return client


@fixture(scope="session")
def bike_id(authenticated_client: LovensClient) -> int:
    bikes = authenticated_client.get_bikes()
    return bikes[0]["id"]
