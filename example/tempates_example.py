from src import NomadAPI
from src.handlers.response import render_template
from rns_mock import dummy_request, RNSMock

app = NomadAPI()
mock = RNSMock()


@app.request("/template")
def template(name: str):
    return render_template("hello.mu", {"name": name})


app.register_handlers(mock)

print(mock.request(*dummy_request("/template", {"name": "test"})))
