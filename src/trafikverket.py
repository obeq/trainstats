from xml.dom.minidom import Document, Element

import requests


TRAFIKVERKET_URL="https://api.trafikinfo.trafikverket.se/v2/data.json"

class Trafikverket():
    def __init__(self, api_key: str):
        self.api_key = api_key


    def create_question(self, object_type: str, filters: list["Filter"] = [], includes: list[str] = [], namespace: str | None = None, schemaversion: str = "1,9", limit: int = 1000) -> str:
        """Create a question for the Trafikverket API."""

        root = Document()

        request = root.createElement("REQUEST")
        root.appendChild(request)

        login = root.createElement("LOGIN")
        login.setAttribute("authenticationkey", self.api_key)
        request.appendChild(login)

        query = root.createElement("QUERY")
        query.setAttribute("objecttype", object_type)
        query.setAttribute("schemaversion", schemaversion)
        query.setAttribute("limit", str(limit))
        if namespace is not None:
            query.setAttribute("namespace", namespace)
        request.appendChild(query)

        filter = root.createElement("FILTER")
        query.appendChild(filter)

        # def get_filter(f: dict) -> Element:
        #     elem = root.createElement(f['type'])
        #     if 'children' in f:
        #         for child in f['children']:
        #             elem.appendChild(get_filter(child))
        #     for key, value in f.items():
        #         if key not in ['type', 'children']:
        #             elem.setAttribute(key, value)
        #     return elem

        for f in filters:
            elem = f.to_xml(root)
            filter.appendChild(elem)

        for i in includes:
            elem = root.createElement("INCLUDE")
            elem.appendChild(root.createTextNode(i))
            query.appendChild(elem)

        return root.toprettyxml()

    def get_data(self, question: str) -> dict:
        """Get data from Trafikverket API."""

        headers = {
            "Content-Type": "text/xml"
        }
        resp = requests.post(TRAFIKVERKET_URL, data=question, headers=headers)

        return resp.json()['RESPONSE']['RESULT'][0]


class Filter:
    def __init__(self, filter_type: str, name: str | None = None, value: str | None = None, children: list["Filter"] | None = None):
        self.children = children or []

        self.filter_type = filter_type
        self.name = name
        self.value = value

    def __repr__(self):
        return f"Filter({self.filter_type}, {self.name}, {self.value}, {self.children})"
    
    def to_xml(self, root: Document) -> Element:
        elem = root.createElement(self.filter_type)
        if self.name is not None:
            elem.setAttribute("name", self.name)
        if self.value is not None:
            elem.setAttribute("value", self.value)
        for child in self.children:
            elem.appendChild(child.to_xml(root))
        return elem

    def __or__(self, other: "Filter"):
        if type(other) != Filter:
            raise ValueError("Can only OR two filters")

        return Filter("OR", children=[self, other])
