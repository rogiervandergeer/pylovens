# pylovens

Python client for the Lovens API.

## Usage

Using the client is as simple as:
```python
from pylovens import LovensClient

client = LovensClient()
client.login("your_username", "your_secret_password")

bikes = client.get_bikes()
```

_Note:_ only authentication with email/password is supported. 
