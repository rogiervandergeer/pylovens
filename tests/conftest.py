from os import environ

from pytest import fixture, skip

from pylovens import LovensClient


@fixture(scope="function")
def client() -> LovensClient:
    return LovensClient("username", "password")


@fixture(scope="session")
def authenticated_client() -> LovensClient:
    try:
        return LovensClient(environ["LOVENS_USERNAME"], environ["LOVENS_PASSWORD"])
    except KeyError:
        skip("Requires authentication.")


@fixture(scope="session")
def bike_id(authenticated_client: LovensClient) -> int:
    bikes = authenticated_client.get_bikes()
    if len(bikes) == 0:
        skip("No bikes found.")
    return bikes[0]["id"]


@fixture(scope="session")
def ride(authenticated_client: LovensClient, bike_id: int) -> dict:
    for ride in authenticated_client.iterate_rides(bike_id):
        return ride
    skip("No rides found.")
