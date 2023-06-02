# pylovens

Python client for the Lovens API.

![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/rogiervandergeer/pylovens/test.yaml) 
![PyPI](https://img.shields.io/pypi/v/pylovens)
![PyPI - License](https://img.shields.io/pypi/l/pylovens)
![PyPI - Downloads](https://img.shields.io/pypi/dm/pylovens) 

## Usage

Using the client is as simple as:
```python
from pylovens import LovensClient

client = LovensClient()
client.login("your_username", "your_secret_password")

bikes = client.get_bikes()
```

_Note:_ only authentication with email/password is supported. 
