from os import environ

from pytest import fixture

from pylovens import LovensClient


@fixture(scope="function")
def client() -> LovensClient:
    return LovensClient()


@fixture(scope="session")
def authenticated_client() -> LovensClient:
    client = LovensClient()
    client.login(environ["LOVENS_USERNAME"], environ["LOVENS_PASSWORD"])
    return client
