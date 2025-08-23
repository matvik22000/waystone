from src import NomadAPI
from src.handlers.request import Request
from test.rns_mock import RNSMock, dummy_request

app = NomadAPI()
mock = RNSMock()


class MyException(Exception):
    pass


@app.request("/test")
def test():
    return "test"


@app.exception(MyException)
def catch_my_exception(e: MyException):
    return str(e)


@app.request("/err")
def err(r: Request):
    raise MyException(r.request_at_utc())


@app.request("/params")
def params(p1: str, p2: int):
    return p1 + " " + str(p2)


@app.request("/default")
def params(p1: str, p2: int = 123):
    return p1 + " " + str(p2)


app.register_handlers(mock)

print(mock.request(*dummy_request("/test", None)))
print(mock.request(*dummy_request("/err", None)))
print(mock.request(*dummy_request("/params", None)))
print(mock.request(*dummy_request("/params", {"p1": "123", "p2": "test"})))
print(mock.request(*dummy_request("/params", {"p2": "test"})))
print(mock.request(*dummy_request("/params", {"p1": "123", "p2": 321})))

print(mock.request(*dummy_request("/default", {"p1": "123", "p2": 321})))
print(mock.request(*dummy_request("/default", {"p1": "123"})))
